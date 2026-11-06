// This small executable checks the actual Foundation-only app sources without a simulator.
// See check-gallery-contracts.sh. It does not replace the native feature/UI tests.
import Foundation

@main
struct GalleryContractChecks {
    static func main() throws {
        var checks = 0
        func check(_ value: Bool, _ message: String) {
            precondition(value, message)
            checks += 1
        }
        let scope = GalleryScope(kind: .video, favorite: .only, trash: .included, rating: .nsfw, sort: .fileOldest, query: "  sea & sky  ")
        let query = Dictionary(uniqueKeysWithValues: scope.queryItems.map { ($0.name, $0.value ?? "") })
        check(query["kind"] == "video", "Kind filter")
        check(query["favorite"] == "true", "Favorite filter")
        check(query["trash"] == nil, "Including trash omits the constraint")
        check(query["content_rating"] == "nsfw", "Rating filter")
        check(query["q"] == "sea & sky", "Trimmed search preserves text")
        check(query["sort"] == "file_created_asc", "Sort contract")
        check(Endpoint.mediaNavigation(id: "m1", scope: scope).queryItems == scope.queryItems, "Navigation matches grid scope")
        let list = Endpoint.galleryList(scope: scope, limit: 48, offset: 96)
        check(list.queryItems?.suffix(2) == [URLQueryItem(name: "limit", value: "48"), URLQueryItem(name: "offset", value: "96")], "Pagination query")
        check(GalleryScope().queryItems.contains(URLQueryItem(name: "trash", value: "false")), "Default excludes trash")
        check(GalleryScope(query: "  ").queryItems.allSatisfy { $0.name != "q" }, "Empty query omitted")
        let favorite = Endpoint.bulkFavorite(ids: ["m1", "m2"], value: true)
        let favoriteBody = try JSONSerialization.jsonObject(with: favorite.body!) as! [String: Any]
        check(favorite.method == "POST" && favorite.path == "/api/v1/media/bulk/favorite", "Favorite endpoint")
        check(favoriteBody["media_ids"] as? [String] == ["m1", "m2"] && favoriteBody["favorite"] as? Bool == true, "Favorite body")
        let trash = Endpoint.bulkTrash(ids: ["m1"], value: false)
        let trashBody = try JSONSerialization.jsonObject(with: trash.body!) as! [String: Any]
        check(trashBody["is_trash"] as? Bool == false && trash.requiresAuth, "Restore body and authentication")
        check(Endpoint.mediaOriginal(id: "m1").path == "/api/v1/media/m1/original", "Original image endpoint")
        let oldJSON = Data(#"{"id":"old","kind":"image","preview_url":"/p"}"#.utf8)
        let old = try JSONDecoder().decode(MobileMediaSummary.self, from: oldJSON)
        check(old.favorite == nil && old.durationSeconds == nil, "Backward-compatible decoding")
        let json = Data(#"{"id":"new","kind":"video","preview_url":"/p","favorite":true,"is_trash":false,"duration_seconds":3661.8,"file_created_at":"2026-11-06T10:20:30.123Z"}"#.utf8)
        let item = try JSONDecoder().decode(MobileMediaSummary.self, from: json)
        check(item.durationLabel == "1:01:01", "Video duration formatting")
        check(item.fileDate != nil, "Fractional ISO file date")
        check(MediaDaySection.group([item, old], sort: .fileNewest).map(\.title) == ["2026-11-06", "日期未知"], "File date groups preserve order")
        check(MediaDaySection.group([item, old], sort: .importedNewest).count == 1, "Missing import dates use unknown group")
        let result = try JSONDecoder().decode(MediaBulkResult.self, from: Data(#"{"requested_count":3,"updated_count":1,"skipped_count":2,"errors":["missing"]}"#.utf8))
        check(result.message.contains("跳过 2 项") && result.message.contains("1 项出错"), "Partial results are not reported as complete success")
        check(LibraryLayout.tileAspectRatio == 0.75, "Default portrait ratio")
        check(LibraryLayout.columnCount(width: 393, accessibilitySize: false) == 3, "Phone columns")
        check(LibraryLayout.columnCount(width: 393, accessibilitySize: true) == 2, "Dynamic Type layout")
        check(LibraryLayout.columnCount(width: 1024, accessibilitySize: false) >= 4, "iPad layout")
        let characterScope = GalleryScope(characterLora: "Character A")
        check(characterScope.queryItems.contains(URLQueryItem(name: "character_lora", value: "Character A")), "Exact character library query")
        check(Endpoint.mediaNavigation(id: "m", scope: characterScope).queryItems == characterScope.queryItems, "Character scope survives navigation")
        let promptScope = PromptUsageScope(promptID: "source - 00042", characterLora: "Character A")
        let promptPage = Endpoint.promptLookup(scope: promptScope, limit: 48, offset: 48)
        check(promptPage.queryItems?.contains(URLQueryItem(name: "group_by_character", value: "true")) == true, "Prompt usage grouped order")
        let promptNavigation = Endpoint.promptNavigation(id: "m", scope: promptScope)
        check(promptNavigation.path == "/api/v1/prompt-registry/usage/navigation", "Prompt uses its own navigation route")
        check(promptNavigation.queryItems?.contains(URLQueryItem(name: "character_lora", value: "Character A")) == true, "Prompt character scope preserved")
        check(promptNavigation.queryItems?.contains(where: { $0.name == "trash" || $0.name == "sort" }) == false, "Library conditions cannot leak into prompt usage")
        check(PromptUsageScope.identifier(source: " Portrait ", index: "00042") == "Portrait - 00042", "Leading zeroes preserved")
        check(PromptUsageScope.identifier(source: "Portrait", index: "-42") == nil, "Negative index rejected")
        check(PromptUsageScope.identifier(source: "Portrait", index: "4x") == nil, "Non-numeric index rejected")
        let rating = Endpoint.setContentRating(id: "m", rating: "nsfw")
        let ratingBody = try JSONSerialization.jsonObject(with: rating.body!) as! [String: String]
        check(rating.method == "PUT" && ratingBody["content_rating"] == "nsfw", "Frontend rating contract")
        let workflow = try JSONDecoder().decode(MediaWorkflowSummary.self, from: Data(#"{"display_fields":{"prompt_id":{"value":"source - 00042"},"character_lora":{"value":"Character A"},"lora_list":{"value":[["Character A",0.8,1.0]]},"prompt":{"value":"Never use embedded prompt as the registered definition"}}}"#.utf8))
        check(workflow.promptID == "source - 00042" && workflow.characterLora == "Character A", "Authoritative display fields")
        check(workflow.loras.count == 1, "Mixed LoRA tuple decoding")
        let usage = try JSONDecoder().decode(PromptRegistryLookup.self, from: Data(#"{"prompt_id":"source - 00042","source":"source","index":"00042","entry":null,"media":[{"id":"m","kind":"video","preview_url":"/p","character_lora":"Character A","content_rating":"nsfw"}],"total_media":1,"limit":48,"offset":0}"#.utf8))
        check(usage.entry == nil && usage.media.count == 1, "Unregistered prompt still has usage")
        check(usage.media.first?.contentRating == "nsfw" && usage.media.first?.characterLora == "Character A", "Usage metadata compatibility")
        check(MediaDaySection.group(usage.media, sort: .importedNewest, byCharacter: true).first?.title == "Character A", "Prompt grid groups by character")
        check(ViewerPreloadPolicy.neighbors(currentID: old.id, candidates: [old, item, item, usage.media[0]]).map(\.id) == [item.id, "m"], "Preload excludes current and duplicate IDs")
        check(!ViewerPreloadPolicy.preloadVideo(item), "Unknown video size is poster-only")
        var smallVideo = item
        smallVideo.byteSize = 1024
        check(ViewerPreloadPolicy.preloadVideo(smallVideo), "Small neighboring video can preload")
        smallVideo.byteSize = ViewerPreloadPolicy.maximumVideoBytes + 1
        check(!ViewerPreloadPolicy.preloadVideo(smallVideo), "Large neighboring video stays poster-only")
        print("PASS: \(checks) gallery contract checks")
    }
}
