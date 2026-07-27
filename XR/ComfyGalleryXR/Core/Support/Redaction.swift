import Foundation

enum Redaction {
    static let hidden = "<private>"

    static func safeErrorDescription(_ error: Error) -> String {
        if let apiError = error as? APIClientError {
            return apiError.errorDescription ?? "The request failed."
        }
        if let validationError = error as? BaseURLValidationError {
            return validationError.errorDescription ?? "The gallery URL is invalid."
        }
        return "The request failed. Check the server and try again."
    }
}
