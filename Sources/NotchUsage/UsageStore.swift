import Foundation

struct ProviderUsage: Codable, Equatable {
    var remainingPercent: Double
    var label: String?
    var resetsAt: Date?
    var secondaryRemainingPercent: Double? = nil
    var secondaryLabel: String? = nil
    var secondaryResetsAt: Date? = nil

    static let placeholder = ProviderUsage(remainingPercent: -1, label: "Waiting for live data", resetsAt: nil)
}

private struct UsageDocument: Codable {
    var claude: ProviderUsage
    var codex: ProviderUsage
}

/// Outcome of a single live-usage request. Replaces the previous
/// "non-200 becomes nil" behaviour so the store can back off on 429 and flag
/// expired credentials on 401 instead of failing silently.
private enum FetchOutcome {
    case success(ProviderUsage)
    case rateLimited(retryAfter: TimeInterval?)
    case unauthorized
    case failed
}

/// Per-provider request health: rate-limit backoff window and credential state.
private struct FetchState {
    var backoffUntil: Date?
    var backoffStep: TimeInterval = 0
    var rateLimited = false
    var tokenExpired = false
}

@MainActor
final class UsageStore: ObservableObject {
    @Published private(set) var claude = ProviderUsage.placeholder
    @Published private(set) var codex = ProviderUsage.placeholder
    @Published private(set) var lastUpdated: Date?
    @Published private(set) var errorMessage: String?

    private var timer: Timer?
    private var lastClaudePoll: Date?
    private var lastCodexRemotePoll: Date?
    private var hasAuthoritativeCodexUsage = false
    private var claudeState = FetchState()
    private var codexState = FetchState()

    // Exponential backoff bounds for 429 responses.
    private static let backoffBase: TimeInterval = 60
    private static let backoffCap: TimeInterval = 900 // 15 minutes

    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }()

    let configURL: URL = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".notch-usage", isDirectory: true)
        .appendingPathComponent("usage.json")

    func start() {
        ensureConfigExists()
        loadCachedLiveUsage()
        Task { await refresh() }
        timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.refresh() }
        }
    }

    func refresh(force: Bool = false) async {
        let now = Date()

        // Query Codex's authoritative service on manual refresh and once per
        // minute. Local session data is only a fallback until that first success.
        // A rate-limit backoff suppresses the request entirely — even on force,
        // since hammering a limited endpoint only prolongs the limit.
        let codexDue = force
            || lastCodexRemotePoll == nil
            || now.timeIntervalSince(lastCodexRemotePoll!) >= 59
        if codexDue && !isBackedOff(codexState, now: now) {
            lastCodexRemotePoll = now
            switch await remoteCodexUsage() {
            case .success(let usage):
                codex = sanitize(usage)
                hasAuthoritativeCodexUsage = true
                codexState.tokenExpired = false
                clearBackoff(&codexState)
                cache(codex, key: "liveCodexUsage")
            case .rateLimited(let retryAfter):
                applyRateLimit(to: &codexState, retryAfter: retryAfter, now: now)
            case .unauthorized:
                codexState.tokenExpired = true
            case .failed:
                break
            }
        }

        // Session logs are only a startup/offline fallback. Once the service has
        // answered, they may contain an older reset time and must never overwrite
        // the authoritative value.
        if !hasAuthoritativeCodexUsage, let localCodex = localCodexUsage() {
            codex = sanitize(localCodex)
            cache(codex, key: "liveCodexUsage")
        }

        let claudeDue = force
            || lastClaudePoll == nil
            || now.timeIntervalSince(lastClaudePoll!) >= 59
        if claudeDue && !isBackedOff(claudeState, now: now) {
            lastClaudePoll = now
            switch await localClaudeUsage() {
            case .success(let usage):
                claude = sanitize(usage)
                claudeState.tokenExpired = false
                clearBackoff(&claudeState)
                cache(claude, key: "liveClaudeUsage")
            case .rateLimited(let retryAfter):
                applyRateLimit(to: &claudeState, retryAfter: retryAfter, now: now)
            case .unauthorized:
                claudeState.tokenExpired = true
            case .failed:
                break
            }
        }

        lastUpdated = now
        errorMessage = statusMessage(now: now)
    }

    func ensureConfigExists() {
        guard !FileManager.default.fileExists(atPath: configURL.path) else { return }
        do {
            try FileManager.default.createDirectory(
                at: configURL.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            let sample = """
            {
              "claude": {
                "remainingPercent": 72,
                "label": "5-hour window",
                "resetsAt": "2026-07-26T02:00:00Z"
              },
              "codex": {
                "remainingPercent": 43,
                "label": "Weekly",
                "resetsAt": "2026-07-28T04:00:00Z"
              }
            }
            """
            try sample.write(to: configURL, atomically: true, encoding: .utf8)
        } catch {
            errorMessage = "Couldn’t create the configuration file."
        }
    }

    // MARK: - Backoff & status

    private func isBackedOff(_ state: FetchState, now: Date) -> Bool {
        guard let until = state.backoffUntil else { return false }
        return now < until
    }

    private func clearBackoff(_ state: inout FetchState) {
        state.backoffUntil = nil
        state.backoffStep = 0
        state.rateLimited = false
    }

    private func applyRateLimit(to state: inout FetchState, retryAfter: TimeInterval?, now: Date) {
        let delay: TimeInterval
        if let retryAfter, retryAfter > 0 {
            // Honour the server's instruction verbatim (capped for sanity).
            delay = min(retryAfter, Self.backoffCap)
            state.backoffStep = delay
        } else {
            // Exponential: 60s, 120s, 240s, … capped at 15min, plus ≤20% jitter
            // so multiple clients don't retry in lockstep.
            let step = state.backoffStep == 0
                ? Self.backoffBase
                : min(state.backoffStep * 2, Self.backoffCap)
            state.backoffStep = step
            delay = min(step + Double.random(in: 0...(step * 0.2)), Self.backoffCap)
        }
        state.backoffUntil = now.addingTimeInterval(delay)
        state.rateLimited = true
    }

    private func statusMessage(now: Date) -> String? {
        var parts: [String] = []

        if claudeState.tokenExpired {
            parts.append("Claude token expired — refresh in Claude Code")
        } else if let until = claudeState.backoffUntil, now < until {
            parts.append("Claude rate limited — retry in \(Self.durationString(until.timeIntervalSince(now)))")
        }

        if codexState.tokenExpired {
            parts.append("Codex token expired — sign in to Codex")
        } else if let until = codexState.backoffUntil, now < until {
            parts.append("Codex rate limited — retry in \(Self.durationString(until.timeIntervalSince(now)))")
        }

        if parts.isEmpty {
            return (claude.remainingPercent < 0 || codex.remainingPercent < 0)
                ? "Some live usage data is unavailable."
                : nil
        }
        return parts.joined(separator: " · ")
    }

    private static func durationString(_ seconds: TimeInterval) -> String {
        let total = max(0, Int(seconds.rounded()))
        if total >= 60 {
            let minutes = total / 60
            let secs = total % 60
            return secs == 0 ? "\(minutes)m" : "\(minutes)m \(secs)s"
        }
        return "\(total)s"
    }

    private static func retryAfter(from response: HTTPURLResponse) -> TimeInterval? {
        guard let value = response.value(forHTTPHeaderField: "Retry-After") else { return nil }
        // Retry-After is either delta-seconds or an HTTP-date.
        if let seconds = TimeInterval(value) { return max(0, seconds) }
        if let date = Self.httpDateFormatter.date(from: value) {
            return max(0, date.timeIntervalSinceNow)
        }
        return nil
    }

    private static let httpDateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: "GMT")
        formatter.dateFormat = "EEE, dd MMM yyyy HH:mm:ss zzz"
        return formatter
    }()

    private func sanitize(_ usage: ProviderUsage) -> ProviderUsage {
        var result = usage
        result.remainingPercent = min(100, max(0, result.remainingPercent))
        if let secondary = result.secondaryRemainingPercent {
            result.secondaryRemainingPercent = min(100, max(0, secondary))
        }
        return result
    }

    private func cache(_ usage: ProviderUsage, key: String) {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        if let data = try? encoder.encode(usage) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }

    private func loadCachedLiveUsage() {
        if let data = UserDefaults.standard.data(forKey: "liveClaudeUsage"),
           let cached = try? decoder.decode(ProviderUsage.self, from: data) {
            claude = cached
        }
        if let data = UserDefaults.standard.data(forKey: "liveCodexUsage"),
           let cached = try? decoder.decode(ProviderUsage.self, from: data) {
            codex = cached
        }
    }

    private func localCodexUsage() -> ProviderUsage? {
        let sessionsURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".codex/sessions", isDirectory: true)
        guard let enumerator = FileManager.default.enumerator(
            at: sessionsURL,
            includingPropertiesForKeys: [.contentModificationDateKey],
            options: [.skipsHiddenFiles]
        ) else { return nil }

        let files = enumerator.compactMap { item -> (URL, Date)? in
            guard let url = item as? URL, url.pathExtension == "jsonl",
                  let values = try? url.resourceValues(forKeys: [.contentModificationDateKey]),
                  let date = values.contentModificationDate else { return nil }
            return (url, date)
        }
        .sorted { $0.1 > $1.1 }
        .prefix(5)

        for (url, _) in files {
            guard let text = try? String(contentsOf: url, encoding: .utf8) else { continue }
            for line in text.split(separator: "\n").reversed() where line.contains("\"rate_limits\":{") {
                guard let data = String(line).data(using: .utf8),
                      let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let payload = root["payload"] as? [String: Any],
                      let limits = payload["rate_limits"] as? [String: Any],
                      let primary = limits["primary"] as? [String: Any],
                      let used = primary["used_percent"] as? Double else { continue }

                let minutes = primary["window_minutes"] as? Int
                let resetSeconds = primary["resets_at"] as? TimeInterval
                let windowLabel: String
                if let minutes, minutes >= 10080 {
                    windowLabel = "Weekly · Live"
                } else if let minutes {
                    windowLabel = "\(minutes / 60)-hour window · Live"
                } else {
                    windowLabel = "Codex local session · Live"
                }
                return ProviderUsage(
                    remainingPercent: 100 - used,
                    label: windowLabel,
                    resetsAt: resetSeconds.map(Date.init(timeIntervalSince1970:))
                )
            }
        }
        return nil
    }

    private func remoteCodexUsage() async -> FetchOutcome {
        let authURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".codex/auth.json")
        guard let authData = try? Data(contentsOf: authURL),
              let auth = try? JSONSerialization.jsonObject(with: authData) as? [String: Any],
              let tokens = auth["tokens"] as? [String: Any],
              let accessToken = tokens["access_token"] as? String,
              let accountID = tokens["account_id"] as? String else { return .unauthorized }

        var request = URLRequest(
            url: URL(string: "https://chatgpt.com/backend-api/wham/usage")!
        )
        request.httpMethod = "GET"
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        request.setValue(accountID, forHTTPHeaderField: "ChatGPT-Account-Id")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse else { return .failed }
            if http.statusCode == 401 || http.statusCode == 403 { return .unauthorized }
            if http.statusCode == 429 { return .rateLimited(retryAfter: Self.retryAfter(from: http)) }
            guard http.statusCode == 200,
                  let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let rateLimit = root["rate_limit"] as? [String: Any],
                  let primary = rateLimit["primary_window"] as? [String: Any],
                  let used = primary["used_percent"] as? Double else { return .failed }

            let resetSeconds = primary["reset_at"] as? TimeInterval
            let windowSeconds = primary["limit_window_seconds"] as? Int
            let label = (windowSeconds ?? 0) >= 604800
                ? "Weekly · Live from service"
                : "Current window · Live from service"
            return .success(ProviderUsage(
                remainingPercent: 100 - used,
                label: label,
                resetsAt: resetSeconds.map(Date.init(timeIntervalSince1970:))
            ))
        } catch {
            return .failed
        }
    }

    private func localClaudeUsage() async -> FetchOutcome {
        guard let creds = claudeCredentials() else { return .unauthorized }
        // Proactively skip a request we know will 401: if Claude Code hasn't
        // refreshed the keychain yet, don't spend a call to discover it's expired.
        if let expiresAt = creds.expiresAt, expiresAt <= Date() { return .unauthorized }

        var request = URLRequest(url: URL(string: "https://api.anthropic.com/api/oauth/usage")!)
        request.httpMethod = "GET"
        request.setValue("Bearer \(creds.token)", forHTTPHeaderField: "Authorization")
        request.setValue("oauth-2025-04-20", forHTTPHeaderField: "anthropic-beta")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse else { return .failed }
            if http.statusCode == 401 || http.statusCode == 403 { return .unauthorized }
            if http.statusCode == 429 { return .rateLimited(retryAfter: Self.retryAfter(from: http)) }
            guard http.statusCode == 200,
                  let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let fiveHour = root["five_hour"] as? [String: Any],
                  let sevenDay = root["seven_day"] as? [String: Any],
                  let fiveHourUsed = fiveHour["utilization"] as? Double,
                  let sevenDayUsed = sevenDay["utilization"] as? Double else { return .failed }

            let fiveReset = fiveHour["resets_at"] as? String
            let weekReset = sevenDay["resets_at"] as? String
            let isoFormatter = ISO8601DateFormatter()
            return .success(ProviderUsage(
                remainingPercent: 100 - sevenDayUsed,
                label: "Weekly · Live",
                resetsAt: weekReset.flatMap(isoFormatter.date(from:)),
                secondaryRemainingPercent: 100 - fiveHourUsed,
                secondaryLabel: "5-hour window · Live",
                secondaryResetsAt: fiveReset.flatMap(isoFormatter.date(from:))
            ))
        } catch {
            return .failed
        }
    }

    /// Reads the Claude Code OAuth blob from the keychain. Returns the access
    /// token and its expiry so callers can detect expiry without a network call.
    /// Read fresh every time — never cached — so a keychain refresh by Claude
    /// Code is picked up on the next poll.
    private func claudeCredentials() -> (token: String, expiresAt: Date?)? {
        let process = Process()
        let output = Pipe()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/security")
        process.arguments = [
            "find-generic-password",
            "-s", "Claude Code-credentials",
            "-w"
        ]
        process.standardOutput = output
        process.standardError = Pipe()

        do {
            try process.run()
            process.waitUntilExit()
            guard process.terminationStatus == 0 else { return nil }
            let data = output.fileHandleForReading.readDataToEndOfFile()
            guard let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let oauth = root["claudeAiOauth"] as? [String: Any],
                  let token = oauth["accessToken"] as? String,
                  !token.isEmpty else { return nil }

            // expiresAt is milliseconds since the Unix epoch.
            var expiresAt: Date?
            if let ms = oauth["expiresAt"] as? Double {
                expiresAt = Date(timeIntervalSince1970: ms / 1000)
            }
            return (token, expiresAt)
        } catch {
            return nil
        }
    }
}
