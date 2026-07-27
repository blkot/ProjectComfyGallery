import Foundation
import Security

enum CredentialStoreError: LocalizedError {
    case keychain(OSStatus)
    case invalidValue

    var errorDescription: String? {
        switch self {
        case .keychain: "The API token could not be saved securely."
        case .invalidValue: "The stored API token is invalid."
        }
    }
}
final class CredentialStore: @unchecked Sendable {
    private let service: String

    init(service: String = "com.comfygallery.xr.api-token") {
        self.service = service
    }

    func saveToken(_ token: String, for profileID: UUID) throws {
        guard let data = token.data(using: .utf8), !token.isEmpty else {
            throw CredentialStoreError.invalidValue
        }
        let account = profileID.uuidString.lowercased()
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
        SecItemDelete(query as CFDictionary)
        var insert = query
        insert[kSecValueData as String] = data
        insert[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(insert as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw CredentialStoreError.keychain(status)
        }
    }

    func token(for profileID: UUID) throws -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: profileID.uuidString.lowercased(),
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess else {
            throw CredentialStoreError.keychain(status)
        }
        guard
            let data = item as? Data,
            let token = String(data: data, encoding: .utf8),
            !token.isEmpty
        else {
            throw CredentialStoreError.invalidValue
        }
        return token
    }

    func deleteToken(for profileID: UUID) throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: profileID.uuidString.lowercased()
        ]
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw CredentialStoreError.keychain(status)
        }
    }
}
