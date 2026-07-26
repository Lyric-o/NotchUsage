import SwiftUI

struct NotchUsageView: View {
    @ObservedObject var store: UsageStore
    let notchWidth: CGFloat
    let onExpansionChanged: (Bool) -> Void
    @State private var expanded = false
    @State private var hovering = false
    @State private var hoveringDetail = false
    @State private var isRefreshing = false

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                ProviderCompactView(name: "Claude", usage: store.claude, tint: Color(red: 0.89, green: 0.47, blue: 0.31), showBars: hovering)
                    .frame(width: 85)

                notch
                    .frame(width: notchWidth, height: 34)

                ProviderCompactView(name: "Codex", usage: store.codex, tint: Color(red: 0.35, green: 0.82, blue: 0.67), showBars: hovering)
                    .frame(width: 85)
            }
            .frame(height: 34)
            .background(.black.opacity(0.92))
            .clipShape(UnevenRoundedRectangle(bottomLeadingRadius: 12, bottomTrailingRadius: 12))
            .onHover { isHovering in
                withAnimation(.easeInOut(duration: 0.18)) {
                    hovering = isHovering
                    if isHovering {
                        expanded = true
                    }
                }
                if !isHovering {
                    Task { @MainActor in
                        try? await Task.sleep(for: .milliseconds(220))
                        if !hovering && !hoveringDetail {
                            withAnimation(.easeInOut(duration: 0.18)) {
                                expanded = false
                            }
                        }
                    }
                }
            }
            .onTapGesture {
                refreshNow()
            }

            if expanded {
                detailPanel
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
        .frame(width: max(440, 170 + notchWidth))
        .frame(maxHeight: .infinity, alignment: .top)
        .onChange(of: expanded) { _, isExpanded in
            onExpansionChanged(isExpanded)
        }
    }

    private func refreshNow() {
        guard !isRefreshing else { return }
        Task { @MainActor in
            isRefreshing = true
            await store.refresh(force: true)
            isRefreshing = false
        }
    }

    private var notch: some View {
        ZStack {
            Color.black
            if isRefreshing {
                ProgressView()
                    .controlSize(.mini)
                    .tint(.white.opacity(0.75))
                    .offset(y: 8)
            } else {
                Capsule()
                    .fill(.white.opacity(0.11))
                    .frame(width: 42, height: 4)
                    .offset(y: 10)
            }
        }
    }

    private var detailPanel: some View {
        HStack(spacing: 18) {
            ProviderDetailView(name: "Claude", usage: store.claude, tint: Color(red: 0.89, green: 0.47, blue: 0.31))
            Divider().overlay(.white.opacity(0.12))
            ProviderDetailView(name: "Codex", usage: store.codex, tint: Color(red: 0.35, green: 0.82, blue: 0.67))
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 12)
        .frame(width: 440, height: 92)
        .background(.ultraThinMaterial)
        .environment(\.colorScheme, .dark)
        .clipShape(UnevenRoundedRectangle(bottomLeadingRadius: 18, bottomTrailingRadius: 18))
        .onHover { isHovering in
            hoveringDetail = isHovering
            if !isHovering && !hovering {
                withAnimation(.easeInOut(duration: 0.18)) {
                    expanded = false
                }
            }
        }
        .overlay(alignment: .bottom) {
            if let errorMessage = store.errorMessage {
                Text(errorMessage)
                    .font(.system(size: 9))
                    .foregroundStyle(.red.opacity(0.9))
                    .offset(y: -2)
            }
        }
    }
}

private struct ProviderCompactView: View {
    let name: String
    let usage: ProviderUsage
    let tint: Color
    let showBars: Bool

    var body: some View {
        Group {
            if showBars {
                fullUsage
            } else {
                numbersOnly
            }
        }
        .padding(.horizontal, 6)
        .transition(.opacity)
    }

    private var fullUsage: some View {
        HStack(spacing: 8) {
            if name == "Claude" {
                claudeBars
            } else {
                Text("Codex")
                    .font(.system(size: 9, weight: .semibold, design: .rounded))
                    .foregroundStyle(.white.opacity(0.75))
                bar
                percentText(usage.remainingPercent, size: 9)
            }
        }
    }

    private var numbersOnly: some View {
        Group {
            if name == "Claude" {
                VStack(spacing: 1) {
                    Text("Claude")
                        .font(.system(size: 9, weight: .semibold, design: .rounded))
                        .foregroundStyle(.white.opacity(0.72))
                    HStack(spacing: 4) {
                        smallTag("5h")
                        percentText(usage.secondaryRemainingPercent ?? usage.remainingPercent, size: 9)
                        smallTag("W")
                        percentText(usage.remainingPercent, size: 9)
                    }
                }
            } else {
                HStack(spacing: 5) {
                    Text("Codex")
                        .font(.system(size: 9, weight: .semibold, design: .rounded))
                        .foregroundStyle(.white.opacity(0.72))
                    percentText(usage.remainingPercent, size: 10)
                }
            }
        }
        .frame(maxWidth: .infinity)
    }

    private func smallTag(_ value: String) -> some View {
        Text(value)
            .font(.system(size: 9, weight: .medium, design: .rounded))
            .foregroundStyle(tint.opacity(0.85))
    }

    private func percentText(_ percent: Double, size: CGFloat) -> some View {
        Text(percent < 0 ? "--" : "\(Int(percent.rounded()))%")
            .font(.system(size: size, weight: .bold, design: .rounded))
            .monospacedDigit()
            .foregroundStyle(.white)
            .fixedSize()
    }

    private var claudeBars: some View {
        VStack(spacing: 3) {
            miniBar(title: "5h", percent: usage.secondaryRemainingPercent ?? usage.remainingPercent)
            miniBar(title: "W", percent: usage.remainingPercent)
        }
    }

    private func miniBar(title: String, percent: Double) -> some View {
        HStack(spacing: 4) {
            Text(title)
                .font(.system(size: 8, weight: .medium, design: .rounded))
                .foregroundStyle(.white.opacity(0.55))
                .frame(width: 12, alignment: .trailing)
            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    Capsule().fill(.white.opacity(0.13))
                    Capsule().fill(tint.gradient)
                        .frame(width: proxy.size.width * max(0, percent) / 100)
                }
            }
            .frame(height: 4)
            Text(percent < 0 ? "--" : "\(Int(percent.rounded()))%")
                .font(.system(size: 8, weight: .bold, design: .rounded))
                .monospacedDigit()
                .foregroundStyle(.white)
                .frame(width: 25, alignment: .trailing)
        }
    }

    private var label: some View {
        HStack(spacing: 5) {
            Circle().fill(tint).frame(width: 6, height: 6)
            Text(name)
                .font(.system(size: 11, weight: .semibold, design: .rounded))
                .foregroundStyle(.white.opacity(0.88))
            Text("\(Int(usage.remainingPercent.rounded()))%")
                .font(.system(size: 11, weight: .bold, design: .rounded))
                .monospacedDigit()
                .foregroundStyle(.white)
        }
        .fixedSize()
    }

    private var bar: some View {
        GeometryReader { proxy in
            ZStack(alignment: .leading) {
                Capsule().fill(.white.opacity(0.13))
                Capsule()
                    .fill(tint.gradient)
                    .frame(width: proxy.size.width * usage.remainingPercent / 100)
            }
        }
        .frame(height: 5)
    }
}

private struct ProviderDetailView: View {
    let name: String
    let usage: ProviderUsage
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(name)
                .font(.system(size: 12, weight: .bold))
            if let secondary = usage.secondaryRemainingPercent {
                resetRow(
                    title: "5-hour",
                    percent: secondary,
                    reset: usage.secondaryResetsAt
                )
            }
            resetRow(
                title: primaryWindowTitle,
                percent: usage.remainingPercent,
                reset: usage.resetsAt
            )
        }
        .frame(maxWidth: .infinity)
    }

    private var primaryWindowTitle: String {
        if name == "Claude" {
            return "Weekly"
        }

        let label = usage.label?.lowercased() ?? ""
        if label.contains("weekly") || label.contains("每周") {
            return "Weekly"
        }
        if label.contains("hour") || label.contains("小时") {
            let hourCount = label.split(whereSeparator: { !$0.isNumber }).first
            if let hourCount {
                return "\(hourCount)-hour"
            }
        }
        return "Current window"
    }

    private func resetRow(title: String, percent: Double, reset: Date?) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            HStack {
                Text(title)
                Spacer()
                Text(percent < 0 ? "--" : "\(Int(percent.rounded()))%")
                    .foregroundStyle(tint)
                    .monospacedDigit()
            }
            Text(reset.map { "Resets: \(Self.resetFormatter.string(from: $0))" } ?? "Reset time unavailable")
                .font(.system(size: 8))
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
        .font(.system(size: 9, weight: .medium))
    }

    private static let resetFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter
    }()
}
