import OSLog

extension Logger {
    static let subsystem = "com.comfygallery.mobile"

    static let api = Logger(subsystem: subsystem, category: "API")
    static let auth = Logger(subsystem: subsystem, category: "Auth")
    static let media = Logger(subsystem: subsystem, category: "Media")
    static let review = Logger(subsystem: subsystem, category: "Review")
    static let persistence = Logger(subsystem: subsystem, category: "Persistence")
    static let lifecycle = Logger(subsystem: subsystem, category: "Lifecycle")
}
