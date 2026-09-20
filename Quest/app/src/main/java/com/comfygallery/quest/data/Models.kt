package com.comfygallery.quest.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class Media(
    val id: String,
    val kind: String,
    val status: String,
    val width: Int? = null,
    val height: Int? = null,
    @SerialName("duration_seconds") val durationSeconds: Double? = null,
    @SerialName("mime_type") val mimeType: String? = null,
    @SerialName("byte_size") val byteSize: Long = 0,
    @SerialName("preview_url") val previewUrl: String,
    @SerialName("playback_url") val playbackUrl: String? = null,
    @SerialName("original_url") val originalUrl: String? = null,
    @SerialName("is_trash") val isTrash: Boolean = false,
    val favorite: Boolean = false,
    @SerialName("spatial_available") val spatialAvailable: Boolean = false,
) {
    val playable: Boolean get() = !isTrash && kind in setOf("image", "video") &&
        status in setOf("ready", "ready_with_warnings")
}

@Serializable
data class MediaPage(val items: List<Media>, val total: Int, val limit: Int, val offset: Int)

@Serializable
data class Navigation(
    @SerialName("media_id") val mediaId: String,
    val position: Int,
    val total: Int,
    @SerialName("previous_id") val previousId: String? = null,
    @SerialName("next_id") val nextId: String? = null,
)

data class GalleryScope(
    val kind: String? = null,
    val favoritesOnly: Boolean = false,
    val oldestFirst: Boolean = false,
) {
    fun parameters(): Map<String, String> = buildMap {
        put("trash", "false")
        put("sort", if (oldestFirst) "file_created_asc" else "file_created_desc")
        kind?.let { put("kind", it) }
        if (favoritesOnly) put("favorite", "true")
    }

    val label: String get() = listOfNotNull(
        when (kind) { "image" -> "Images"; "video" -> "Videos"; else -> "All media" },
        if (favoritesOnly) "Favorites" else null,
        if (oldestFirst) "Oldest first" else "Newest first",
    ).joinToString(" · ")
}

class GalleryFailure(val status: Int, val code: String, message: String) : Exception(message)

interface GalleryApi {
    suspend fun verify()
    suspend fun page(scope: GalleryScope, offset: Int): MediaPage
    suspend fun detail(id: String): Media
    suspend fun navigation(id: String, scope: GalleryScope): Navigation
    suspend fun favorite(id: String, value: Boolean)
}

data class PageState(
    val items: List<Media> = emptyList(),
    val nextOffset: Int = 0,
    val exhausted: Boolean = false,
    val serverTotal: Int = 0,
) {
    fun append(page: MediaPage): PageState {
        require(page.offset == nextOffset) { "The server returned a different page offset." }
        require(page.limit > 0) { "The server returned an invalid page size." }
        val next = page.offset + page.items.size
        return PageState(
            (items + page.items.filter { it.playable }).distinctBy { it.id },
            next,
            page.items.size < page.limit || next >= page.total,
            page.total,
        )
    }
}

enum class Direction { Previous, Next }

/** Both grid and Viewer use the same playable policy; traversal is cancelable and bounded. */
suspend fun GalleryApi.neighbor(id: String, scope: GalleryScope, direction: Direction): Media? {
    var anchor = id
    val visited = mutableSetOf(id)
    repeat(64) {
        val nav = navigation(anchor, scope)
        val candidate = (if (direction == Direction.Next) nav.nextId else nav.previousId) ?: return null
        if (!visited.add(candidate)) throw GalleryFailure(0, "NAVIGATION_CYCLE", "Refresh the Library to continue navigation.")
        val media = detail(candidate)
        if (media.playable) return media
        anchor = candidate
    }
    throw GalleryFailure(0, "NAVIGATION_LIMIT", "Too many unavailable items. Choose another item in the Library.")
}
