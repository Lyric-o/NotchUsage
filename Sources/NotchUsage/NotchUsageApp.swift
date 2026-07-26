import SwiftUI
import AppKit
import ServiceManagement

@main
struct NotchUsageApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    var body: some Scene {
        Settings {
            EmptyView()
        }
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var panelController: NotchPanelController?
    private var statusItem: NSStatusItem?
    private var launchAtLoginItem: NSMenuItem?
    private let store = UsageStore()

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        panelController = NotchPanelController(store: store)
        panelController?.show()
        installMenuBarItem()
        enableLaunchAtLoginByDefault()
        store.start()
    }

    private func installMenuBarItem() {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        item.button?.image = NSImage(systemSymbolName: "gauge.with.dots.needle.33percent", accessibilityDescription: "Notch Usage")

        let menu = NSMenu()
        menu.addItem(withTitle: "Refresh Usage", action: #selector(refresh), keyEquivalent: "r")
        menu.addItem(withTitle: "Open Configuration…", action: #selector(openConfig), keyEquivalent: ",")
        let loginItem = NSMenuItem(
            title: "Launch at Login",
            action: #selector(toggleLaunchAtLogin),
            keyEquivalent: ""
        )
        loginItem.target = self
        menu.addItem(loginItem)
        launchAtLoginItem = loginItem
        updateLaunchAtLoginMenu()
        menu.addItem(.separator())
        menu.addItem(withTitle: "Quit NotchUsage", action: #selector(quit), keyEquivalent: "q")
        menu.items.forEach { $0.target = self }
        item.menu = menu
        statusItem = item
    }

    @objc private func refresh() {
        Task { await store.refresh(force: true) }
    }

    @objc private func openConfig() {
        store.ensureConfigExists()
        NSWorkspace.shared.open(store.configURL)
    }

    @objc private func quit() {
        NSApp.terminate(nil)
    }

    @objc private func toggleLaunchAtLogin() {
        do {
            if SMAppService.mainApp.status == .enabled {
                try SMAppService.mainApp.unregister()
            } else {
                try SMAppService.mainApp.register()
            }
        } catch {
            let alert = NSAlert()
            alert.messageText = "Couldn’t Change Launch at Login"
            alert.informativeText = error.localizedDescription
            alert.runModal()
        }
        updateLaunchAtLoginMenu()
    }

    private func enableLaunchAtLoginByDefault() {
        let defaults = UserDefaults.standard
        guard !defaults.bool(forKey: "launchAtLoginConfigured") else {
            updateLaunchAtLoginMenu()
            return
        }
        do {
            if SMAppService.mainApp.status == .notRegistered {
                try SMAppService.mainApp.register()
            }
            defaults.set(true, forKey: "launchAtLoginConfigured")
        } catch {
            // Keep the switch off; the user can retry from the menu.
        }
        updateLaunchAtLoginMenu()
    }

    private func updateLaunchAtLoginMenu() {
        launchAtLoginItem?.state = SMAppService.mainApp.status == .enabled ? .on : .off
    }
}
