import SwiftUI

@MainActor
@Observable
final class SettingsFeature {
    var showDisconnectConfirmation = false
    var privacyCoverEnabled = false
    var cacheSizeDescription: String = "Calculating..."
    var isClearingCache = false

    private let connectionService: ConnectionService
    private let mediaRepository: MediaRepository

    init(connectionService: ConnectionService, mediaRepository: MediaRepository) {
        self.connectionService = connectionService
        self.mediaRepository = mediaRepository
    }

    func disconnect() async {
        await connectionService.disconnect()
    }

    func clearCache() async {
        isClearingCache = true
        await mediaRepository.clearAllCaches()
        cacheSizeDescription = "0 bytes"
        isClearingCache = false
    }
}
