import Foundation

enum Endpoint {
    case health
    case authSession
    case mediaList(kind: MediaKind?, evaluationState: EvaluationState?, trash: Bool?, sort: String?, limit: Int, offset: Int)
    case mediaPreview(id: String)
    case mediaPlayback(id: String)
    case mediaOriginal(id: String)
    case mediaDetail(id: String)
    case galleryList(scope: GalleryScope, limit: Int, offset: Int)
    case mediaNavigation(id: String, scope: GalleryScope)
    case bulkFavorite(ids: [String], value: Bool)
    case bulkTrash(ids: [String], value: Bool)
    case setContentRating(id: String, rating: String)
    case mediaWorkflow(id: String)
    case characterLoras(query: String)
    case promptSources(query: String)
    case promptLookup(scope: PromptUsageScope, limit: Int, offset: Int)
    case promptNavigation(id: String, scope: PromptUsageScope)
    case reviewSummary
    case reviewSessions(limit: Int?)
    case createReviewSession(CreateSessionRequest)
    case getReviewSession(id: String)
    case patchReviewSession(id: String, PatchSessionBody)
    case deleteReviewSession(id: String)
    case reviewItem(sessionID: String, position: Int)
    case setScore(evaluationID: String, criterionVersionID: String, SetScoreRequest)
    case deleteScore(evaluationID: String, criterionVersionID: String, DeleteScoreRequest)
    case trash(evaluationID: String, TrashRestoreRequest)
    case restore(evaluationID: String, TrashRestoreRequest)

    var path: String {
        switch self {
        case .health: return "/health/live"
        case .authSession: return "/api/v1/auth/session"
        case .mediaList: return "/api/v1/media"
        case .mediaPreview(let id): return "/api/v1/media/\(id)/preview"
        case .mediaPlayback(let id): return "/api/v1/media/\(id)/playback"
        case .mediaOriginal(let id): return "/api/v1/media/\(id)/original"
        case .mediaDetail(let id): return "/api/v1/media/\(id)"
        case .galleryList: return "/api/v1/media"
        case .mediaNavigation(let id, _): return "/api/v1/media/\(id)/navigation"
        case .bulkFavorite: return "/api/v1/media/bulk/favorite"
        case .bulkTrash: return "/api/v1/media/bulk/trash"
        case .setContentRating(let id, _): return "/api/v1/media/\(id)/content-rating"
        case .mediaWorkflow(let id): return "/api/v1/media/\(id)/workflow"
        case .characterLoras: return "/api/v1/prompt-registry/character-loras"
        case .promptSources: return "/api/v1/prompt-registry/sources"
        case .promptLookup: return "/api/v1/prompt-registry/lookup"
        case .promptNavigation: return "/api/v1/prompt-registry/usage/navigation"
        case .reviewSummary: return "/api/v1/review/summary"
        case .reviewSessions: return "/api/v1/review-sessions"
        case .createReviewSession: return "/api/v1/review-sessions"
        case .getReviewSession(let id): return "/api/v1/review-sessions/\(id)"
        case .patchReviewSession(let id, _): return "/api/v1/review-sessions/\(id)"
        case .deleteReviewSession(let id): return "/api/v1/review-sessions/\(id)"
        case .reviewItem(let sessionID, let position): return "/api/v1/review-sessions/\(sessionID)/items/\(position)"
        case .setScore(let evaluationID, let criterionVersionID, _): return "/api/v1/evaluations/\(evaluationID)/scores/\(criterionVersionID)"
        case .deleteScore(let evaluationID, let criterionVersionID, _): return "/api/v1/evaluations/\(evaluationID)/scores/\(criterionVersionID)"
        case .trash(let evaluationID, _): return "/api/v1/evaluations/\(evaluationID)/trash"
        case .restore(let evaluationID, _): return "/api/v1/evaluations/\(evaluationID)/restore"
        }
    }

    var method: String {
        switch self {
        case .health, .authSession, .mediaList, .mediaPreview, .mediaPlayback,
             .mediaOriginal, .mediaDetail, .galleryList, .mediaNavigation, .mediaWorkflow,
             .characterLoras, .promptSources, .promptLookup, .promptNavigation,
             .reviewSummary, .reviewSessions, .getReviewSession, .reviewItem:
            return "GET"
        case .createReviewSession, .trash, .restore, .bulkFavorite, .bulkTrash:
            return "POST"
        case .patchReviewSession:
            return "PATCH"
        case .setScore, .setContentRating:
            return "PUT"
        case .deleteScore, .deleteReviewSession:
            return "DELETE"
        }
    }

    var requiresAuth: Bool {
        switch self {
        case .health: return false
        default: return true
        }
    }

    var queryItems: [URLQueryItem]? {
        switch self {
        case .mediaWorkflow:
            return [URLQueryItem(name: "node_limit", value: "1"), URLQueryItem(name: "edge_limit", value: "1")]
        case .characterLoras(let query):
            return [URLQueryItem(name: "limit", value: "200"), URLQueryItem(name: "q", value: query)]
        case .promptSources(let query):
            return [URLQueryItem(name: "limit", value: "50"), URLQueryItem(name: "q", value: query)]
        case .promptLookup(let scope, let limit, let offset):
            return scope.queryItems + [URLQueryItem(name: "group_by_character", value: "true"), URLQueryItem(name: "limit", value: String(limit)), URLQueryItem(name: "offset", value: String(offset))]
        case .promptNavigation(let id, let scope):
            return scope.queryItems + [URLQueryItem(name: "media_id", value: id)]
        case .galleryList(let scope, let limit, let offset):
            return scope.queryItems + [URLQueryItem(name: "limit", value: String(limit)), URLQueryItem(name: "offset", value: String(offset))]
        case .mediaNavigation(_, let scope):
            return scope.queryItems
        case .mediaList(let kind, let evaluationState, let trash, let sort, let limit, let offset):
            var items: [URLQueryItem] = [
                URLQueryItem(name: "limit", value: String(limit)),
                URLQueryItem(name: "offset", value: String(offset)),
            ]
            if let kind = kind { items.append(URLQueryItem(name: "kind", value: kind.rawValue)) }
            if let state = evaluationState { items.append(URLQueryItem(name: "evaluation_state", value: state.rawValue)) }
            if let trash = trash { items.append(URLQueryItem(name: "trash", value: String(trash))) }
            if let sort = sort { items.append(URLQueryItem(name: "sort", value: sort)) }
            return items
        case .reviewSessions(let limit):
            if let limit = limit {
                return [URLQueryItem(name: "limit", value: String(limit))]
            }
            return nil
        default:
            return nil
        }
    }

    var body: Data? {
        let encoder = JSONEncoder()
        switch self {
        case .setContentRating(_, let rating):
            return try? JSONSerialization.data(withJSONObject: ["content_rating": rating])
        case .bulkFavorite(let ids, let value):
            return try? JSONSerialization.data(withJSONObject: ["media_ids": ids, "favorite": value])
        case .bulkTrash(let ids, let value):
            return try? JSONSerialization.data(withJSONObject: ["media_ids": ids, "is_trash": value])
        case .createReviewSession(let req):
            return try? encoder.encode(req)
        case .patchReviewSession(_, let body):
            return try? encoder.encode(body)
        case .setScore(_, _, let req):
            return try? encoder.encode(req)
        case .deleteScore(_, _, let req):
            return try? encoder.encode(req)
        case .trash(_, let req), .restore(_, let req):
            return try? encoder.encode(req)
        default:
            return nil
        }
    }
}
