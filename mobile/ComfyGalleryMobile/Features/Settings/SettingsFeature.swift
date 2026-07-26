import SwiftUI

@MainActor
@Observable
final class SettingsFeature {
    var showDisconnectConfirmed = false
    var showDisconnectConfirmation = false
    var privacyCoverEnabled = false
    var cacheSizeDescription: String = ""
    var isClearingCache = false
    var appVersionDescription: String = ""

    private let connectionService: ConnectionService
    private let mediaRepository: MediaRepository

    init(connectionService: ConnectionService, mediaRepository: MediaRepository) {
        self.connectionService = connectionService
        self.mediaRepository = mediaRepository
        self.appVersionDescription = Self.readAppVersion()
    }

    func refreshCacheSize() async {
        let bytes = await mediaRepository.currentCacheBytes()
        cacheSizeDescription = Self.formatBytes(bytes)
    }

    func disconnect() async {
        await connectionService.disconnect()
    }

    func clearCache() async {
        isClearingCache = true
        await mediaRepository.clearAllCaches()
        await refreshCacheSize()
        isClearingCache = false
    }

    private static func readAppVersion() -> String {
        let info = Bundle.main.infoDictionary
        let short = info?["CFBundleShortVersionString"] as? String ?? "0.0.0"
        let build = info?["CFBundleVersion"] as? String ?? "0"
        return "\(short) (\(build))"
    }

    private static func formatBytes(_ bytes: Int64) -> String {
        let formatter = ByteCountFormatter()
        formatter.allowedUnits = [.useKB, .useMB, .useGB]
        formatter.countStyle = .file
        return formatter.string(fromByteCount: bytes)
    }
}
