import Foundation
import SwiftData

@MainActor
final class AppEnvironment {
    let persistence: PersistenceStore
    let credentials: CredentialStore
    let api: APIClient
    let cache: MediaCache
    let galleryRepository: GalleryRepository
    let mediaRepository: MediaRepository

    init(container: ModelContainer) throws {
        persistence = PersistenceStore(container: container)
        credentials = CredentialStore()
        api = APIClient()
        cache = try MediaCache(modelContainer: container)
        let pipeline = ImagePipeline(api: api, cache: cache)
        galleryRepository = GalleryRepository(api: api)
        mediaRepository = MediaRepository(api: api, cache: cache, imagePipeline: pipeline)
    }
}
