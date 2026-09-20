package com.comfygallery.quest

import com.comfygallery.quest.data.*
import com.comfygallery.quest.library.*
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test

private fun media(id: String, kind: String = "image", status: String = "ready", favorite: Boolean = false) =
    Media(id, kind, status, previewUrl = "/preview/$id", playbackUrl = "/play/$id", originalUrl = "/original/$id", favorite = favorite)

private class FakeApi : GalleryApi {
    var pageCall: suspend (GalleryScope, Int) -> MediaPage = { _, offset -> MediaPage(emptyList(), 0, 48, offset) }
    var detailCall: suspend (String) -> Media = { media(it) }
    var navCall: suspend (String, GalleryScope) -> Navigation = { id, _ -> Navigation(id, 0, 0) }
    var favoriteCall: suspend (String, Boolean) -> Unit = { _, _ -> }
    override suspend fun verify() = Unit
    override suspend fun page(scope: GalleryScope, offset: Int) = pageCall(scope, offset)
    override suspend fun detail(id: String) = detailCall(id)
    override suspend fun navigation(id: String, scope: GalleryScope) = navCall(id, scope)
    override suspend fun favorite(id: String, value: Boolean) = favoriteCall(id, value)
}

@OptIn(ExperimentalCoroutinesApi::class)
class GalleryStoreTest {
    @Test fun `approaching the grid end fetches the next page without a button`() = runTest {
        val api = FakeApi()
        val offsets = mutableListOf<Int>()
        api.pageCall = { _, offset -> offsets += offset; MediaPage(List(48) { media("${offset + it}") }, 144, 48, offset) }
        val store = GalleryStore(api, backgroundScope, {}, {}, {})
        store.refresh(); runCurrent()
        store.viewportChanged(15); runCurrent()
        assertEquals(listOf(0), offsets)
        store.viewportChanged(40); store.viewportChanged(40); runCurrent()
        assertEquals(listOf(0, 48), offsets)
        assertEquals(96, store.state.value.page.items.size)
        store.close()
    }

    @Test fun `automatic paging stops on errors and retries only explicitly`() = runTest {
        val api = FakeApi()
        var calls = 0
        api.pageCall = { _, offset ->
            calls++
            if (offset > 0) throw GalleryFailure(503, "offline", "Offline")
            MediaPage(List(48) { media("$it") }, 1000, 48, offset)
        }
        val store = GalleryStore(api, backgroundScope, {}, {}, {})
        store.refresh(); runCurrent()
        store.viewportChanged(47); runCurrent()
        repeat(5) { store.viewportChanged(47); runCurrent() }
        assertEquals(2, calls)
        assertNotNull(store.state.value.libraryError)
        store.loadMore(); runCurrent()
        assertEquals(3, calls)
        store.close()
    }

    @Test fun `raw offsets advance over hidden and duplicate media`() {
        val first = PageState().append(MediaPage(listOf(media("a"), media("b", status = "pending")), 6, 2, 0))
        val second = first.append(MediaPage(listOf(media("a"), media("c", "audio")), 6, 2, 2))
        assertEquals(listOf("a"), second.items.map { it.id })
        assertEquals(4, second.nextOffset)
        assertFalse(second.exhausted)
        assertThrows(IllegalArgumentException::class.java) { second.append(MediaPage(emptyList(), 6, 2, 0)) }
    }

    @Test fun `filtering only batches are bounded and continuation preserves offset`() = runTest {
        val api = FakeApi()
        val offsets = mutableListOf<Int>()
        api.pageCall = { _, offset -> offsets += offset; MediaPage(List(48) { media("$offset-$it", status = "pending") }, 1000, 48, offset) }
        val store = GalleryStore(api, backgroundScope, {}, {}, {})
        store.refresh(); runCurrent()
        assertEquals(listOf(0, 48, 96, 144), offsets)
        assertEquals(192, store.state.value.page.nextOffset)
        assertTrue(store.state.value.page.items.isEmpty())
        assertFalse(store.state.value.loading)
        repeat(4) { store.viewportChanged(-1); runCurrent() }
        assertEquals(4, offsets.size)
        assertTrue(store.state.value.scanPaused)
        store.loadMore(); runCurrent()
        assertEquals(192, offsets[4])
        store.close()
    }

    @Test fun `old filter completion cannot overwrite current scope`() = runTest {
        val api = FakeApi()
        val pending = CompletableDeferred<MediaPage>()
        api.pageCall = { filter, offset ->
            if (filter.kind == null) withContext(NonCancellable) { pending.await() }
            else MediaPage(listOf(media("new", "video")), 1, 48, offset)
        }
        val store = GalleryStore(api, backgroundScope, {}, {}, {})
        store.refresh(); runCurrent()
        store.refresh(GalleryScope(kind = "video")); runCurrent()
        pending.complete(MediaPage(listOf(media("old")), 1, 48, 0)); runCurrent()
        assertEquals(listOf("new"), store.state.value.page.items.map { it.id })
        assertFalse(store.state.value.loading)
        store.close()
    }

    @Test fun `new selection rejects late detail and closed viewer cannot reopen`() = runTest {
        val api = FakeApi()
        val old = CompletableDeferred<Media>()
        val shown = mutableListOf<String?>()
        api.detailCall = { id -> if (id == "old") withContext(NonCancellable) { old.await() } else media(id) }
        val store = GalleryStore(api, backgroundScope, { shown += it?.media?.id }, {}, {})
        store.open("old"); runCurrent()
        store.open("new"); runCurrent()
        old.complete(media("old")); runCurrent()
        assertEquals("new", store.state.value.selection!!.media.id)
        assertFalse(shown.contains("old"))
        store.closeViewer(); runCurrent()
        assertNull(store.state.value.selection)
        assertFalse(store.state.value.viewerOpen)
        store.close()
    }

    @Test fun `image timer starts on success and focus loss requires explicit resume`() = runTest {
        val api = FakeApi()
        api.navCall = { id, _ -> Navigation(id, 0, 2, nextId = if (id == "a") "b" else null) }
        val store = GalleryStore(api, backgroundScope, {}, {}, {})
        store.setActive(true); store.open("a"); runCurrent()
        store.setSequence(true)
        advanceTimeBy(6000); runCurrent()
        assertEquals("a", store.state.value.selection!!.media.id)
        store.imageLoaded(store.state.value.selection!!.generation)
        advanceTimeBy(4999); runCurrent()
        assertEquals("a", store.state.value.selection!!.media.id)
        advanceTimeBy(1); runCurrent()
        assertEquals("b", store.state.value.selection!!.media.id)
        store.imageLoaded(store.state.value.selection!!.generation)
        store.setActive(false); store.setActive(true)
        advanceTimeBy(6000); runCurrent()
        assertFalse(store.state.value.sequence)
        assertEquals("b", store.state.value.selection!!.media.id)
        store.close()
    }

    @Test fun `sequence overrides loop without changing preference and rejects stale ended events`() = runTest {
        val api = FakeApi()
        api.detailCall = { media(it, "video") }
        api.navCall = { id, _ -> Navigation(id, 0, 2, nextId = if (id == "a") "b" else null) }
        val store = GalleryStore(api, backgroundScope, {}, {}, {})
        store.setActive(true); store.open("a"); runCurrent(); store.setSequence(true)
        val first = store.state.value.selection!!.generation
        store.videoEnded(first); runCurrent()
        assertEquals("b", store.state.value.selection!!.media.id)
        assertTrue(store.state.value.loop)
        store.videoEnded(first); runCurrent()
        assertTrue(store.state.value.sequence)
        store.videoEnded(store.state.value.selection!!.generation); runCurrent()
        assertFalse(store.state.value.sequence)
        assertTrue(store.state.value.loop)
        store.close()
    }

    @Test fun `callbacks from a disconnected profile cannot expire a new connection`() = runTest {
        var expired = 0
        val store = GalleryStore(FakeApi(), backgroundScope, {}, {}, { expired++ })
        store.open("a"); runCurrent()
        val owner = store.state.value.selection!!.generation
        store.close()
        store.mediaFailed(owner, unauthorized = true)
        store.mediaAuthExpired()
        store.imageLoaded(owner)
        store.videoEnded(owner)
        assertEquals(0, expired)
        assertNull(store.state.value.selection)
    }

    @Test fun `late favorite failure cannot replace a newer viewers error state`() = runTest {
        val api = FakeApi()
        val mutation = CompletableDeferred<Unit>()
        api.favoriteCall = { _, _ -> mutation.await() }
        val store = GalleryStore(api, backgroundScope, {}, {}, {})
        store.open("a"); runCurrent(); store.favorite(); runCurrent()
        store.open("b"); runCurrent()
        mutation.completeExceptionally(GalleryFailure(500, "failed", "Favorite failed")); runCurrent()
        assertEquals("b", store.state.value.selection!!.media.id)
        assertNull(store.state.value.viewerError)
        assertFalse(store.state.value.favoriteSaving)
        store.close()
    }

    @Test fun `viewer scope stays captured when library changes and skips unready neighbors`() = runTest {
        val api = FakeApi()
        val scopes = mutableListOf<GalleryScope>()
        api.navCall = { id, filter -> scopes += filter; Navigation(id, 0, 3, nextId = when (id) { "a" -> "pending"; "pending" -> "b"; else -> null }) }
        api.detailCall = { media(it, status = if (it == "pending") "pending" else "ready") }
        val store = GalleryStore(api, backgroundScope, {}, {}, {})
        store.open("a"); runCurrent()
        store.refresh(GalleryScope(kind = "video", favoritesOnly = true)); runCurrent()
        store.navigate(Direction.Next); runCurrent()
        assertEquals("b", store.state.value.selection!!.media.id)
        assertEquals(listOf(GalleryScope(), GalleryScope()), scopes)
        store.close()
    }

    @Test fun `unfavorite retains current content and removes navigation anchor`() = runTest {
        val api = FakeApi()
        api.detailCall = { media(it, favorite = true) }
        val store = GalleryStore(api, backgroundScope, {}, {}, {})
        store.refresh(GalleryScope(favoritesOnly = true)); runCurrent()
        store.setActive(true); store.open("a"); runCurrent(); store.setSequence(true)
        store.favorite(); runCurrent()
        assertEquals("a", store.state.value.selection!!.media.id)
        assertFalse(store.state.value.selection!!.media.favorite)
        assertFalse(store.state.value.inScope)
        assertFalse(store.state.value.sequence)
        store.close()
    }

    @Test fun `401 requests reconnection while navigation cycles fail recoverably`() = runTest {
        val api = FakeApi()
        var expired = 0
        val store = GalleryStore(api, backgroundScope, {}, {}, { expired++ })
        api.pageCall = { _, _ -> throw GalleryFailure(401, "unauthorized", "rejected") }
        store.refresh(); runCurrent()
        assertEquals(1, expired)
        api.navCall = { id, _ -> Navigation(id, 0, 2, nextId = id) }
        store.open("a"); runCurrent(); store.navigate(Direction.Next); runCurrent()
        assertNotNull(store.state.value.viewerError)
        assertEquals("a", store.state.value.selection!!.media.id)
        store.close()
    }
}
