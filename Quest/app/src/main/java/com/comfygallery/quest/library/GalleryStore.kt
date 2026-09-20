package com.comfygallery.quest.library

import com.comfygallery.quest.data.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

data class Selection(val media: Media, val scope: GalleryScope, val generation: Long)

data class GalleryState(
    val scope: GalleryScope = GalleryScope(),
    val page: PageState = PageState(),
    val loading: Boolean = false,
    val libraryError: String? = null,
    val scanPaused: Boolean = false,
    val viewerOpen: Boolean = false,
    val selection: Selection? = null,
    val selectionLoading: Boolean = false,
    val viewerError: String? = null,
    val notice: String? = null,
    val inScope: Boolean = true,
    val favoriteSaving: Boolean = false,
    val sequence: Boolean = false,
    val loop: Boolean = true,
)

/** Main-thread state owner. A server profile owns one store and all of its jobs. */
class GalleryStore(
    private val api: GalleryApi,
    parentScope: CoroutineScope,
    private val onSelection: (Selection?) -> Unit,
    private val onPause: () -> Unit,
    private val onUnauthorized: () -> Unit,
) {
    private val jobs = SupervisorJob(parentScope.coroutineContext[Job])
    private val scope = CoroutineScope(parentScope.coroutineContext + jobs)
    private val mutable = MutableStateFlow(GalleryState())
    val state = mutable.asStateFlow()
    private var pageJob: Job? = null
    private var viewerJob: Job? = null
    private var timer: Job? = null
    private var pageRevision = 0L
    private var viewerRevision = 0L
    private var generation = 0L
    private var imageReady = false
    private var active = false

    fun refresh(filter: GalleryScope = state.value.scope) {
        pageRevision++
        pageJob?.cancel()
        mutable.update { it.copy(scope = filter, page = PageState(), loading = false, libraryError = null, scanPaused = false) }
        loadMore()
    }

    fun loadMore() {
        val snapshot = state.value
        if (snapshot.loading || snapshot.page.exhausted || !jobs.isActive) return
        val revision = pageRevision
        mutable.update { it.copy(loading = true, libraryError = null, scanPaused = false) }
        pageJob = scope.launch {
            try {
                var page = snapshot.page
                // Stop after four pages without visible progress; do not auto-scan an entire library.
                for (attempt in 0 until 4) {
                    page = page.append(api.page(snapshot.scope, page.nextOffset))
                    if (revision != pageRevision || !isActive) return@launch
                    mutable.update { it.copy(page = page) }
                    if (page.exhausted || page.items.size > snapshot.page.items.size) break
                }
                mutable.update { it.copy(scanPaused = !page.exhausted && page.items.size == snapshot.page.items.size) }
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                if (revision == pageRevision && isActive) report(e, viewer = false)
            } finally {
                if (revision == pageRevision) mutable.update { it.copy(loading = false) }
            }
        }
    }

    fun viewportChanged(lastVisibleIndex: Int) {
        val current = state.value
        if (current.loading || current.libraryError != null || current.scanPaused || current.page.exhausted) return
        if (current.page.items.isEmpty() || lastVisibleIndex >= current.page.items.size - 12) loadMore()
    }

    fun open(id: String) {
        val capturedScope = state.value.scope
        val revision = beginSelection()
        mutable.update { it.copy(viewerOpen = true, selection = null, selectionLoading = true, inScope = true) }
        onSelection(null)
        viewerJob = scope.launch {
            try {
                val media = api.detail(id)
                if (revision != viewerRevision || !isActive) return@launch
                require(media.playable) { "This item is not ready to view." }
                commit(media, capturedScope)
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                if (revision == viewerRevision && isActive) report(e, viewer = true)
            } finally {
                if (revision == viewerRevision) mutable.update { it.copy(selectionLoading = false) }
            }
        }
    }

    fun navigate(direction: Direction) {
        val current = state.value.selection ?: return
        if (!state.value.inScope || state.value.selectionLoading) return
        val revision = beginSelection()
        mutable.update { it.copy(selectionLoading = true) }
        viewerJob = scope.launch {
            try {
                val next = api.neighbor(current.media.id, current.scope, direction)
                if (revision != viewerRevision || !isActive) return@launch
                if (next == null) {
                    mutable.update { it.copy(sequence = false, notice = "End of this view. Choose another item or press Play.") }
                } else commit(next, current.scope)
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                if (revision == viewerRevision && isActive) {
                    if (e is GalleryFailure && e.status == 404) {
                        mutable.update { it.copy(inScope = false) }
                        refresh()
                    }
                    report(e, viewer = true)
                }
            } finally {
                if (revision == viewerRevision) mutable.update { it.copy(selectionLoading = false) }
            }
        }
    }

    private fun beginSelection(): Long {
        viewerRevision++
        viewerJob?.cancel()
        timer?.cancel()
        onPause()
        mutable.update { it.copy(viewerError = null, notice = null) }
        return viewerRevision
    }

    private fun commit(media: Media, capturedScope: GalleryScope) {
        val selection = Selection(media, capturedScope, ++generation)
        imageReady = false
        mutable.update { it.copy(selection = selection, viewerError = null, notice = null, inScope = true) }
        onSelection(selection)
    }

    fun favorite() {
        val selection = state.value.selection ?: return
        if (state.value.favoriteSaving) return
        mutable.update { it.copy(favoriteSaving = true) }
        scope.launch {
            try {
                val value = !selection.media.favorite
                api.favorite(selection.media.id, value)
                if (!isActive) return@launch
                mutable.update { current ->
                    val same = current.selection?.generation == selection.generation
                    val removed = same && selection.scope.favoritesOnly && !value
                    current.copy(
                        page = current.page.copy(items = current.page.items.map { if (it.id == selection.media.id) it.copy(favorite = value) else it }
                            .filter { !current.scope.favoritesOnly || it.favorite }),
                        selection = if (same) selection.copy(media = selection.media.copy(favorite = value)) else current.selection,
                        inScope = if (removed) false else current.inScope,
                        sequence = if (removed) false else current.sequence,
                        notice = if (removed) "Removed from Favorites. Select another item in the Library to continue." else current.notice,
                    )
                }
                // Favorite mutations can shift raw offsets in a Favorite-only Library.
                if (state.value.scope.favoritesOnly) refresh()
                if (!state.value.inScope) timer?.cancel()
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                if (isActive && (state.value.selection?.generation == selection.generation || (e is GalleryFailure && e.status == 401))) {
                    report(e, viewer = true)
                }
            } finally { mutable.update { it.copy(favoriteSaving = false) } }
        }
    }

    fun setLoop(value: Boolean) { mutable.update { it.copy(loop = value) } }

    fun setSequence(value: Boolean) {
        timer?.cancel()
        mutable.update { it.copy(sequence = value && active && it.inScope && it.viewerError == null && it.selection != null) }
        scheduleImage()
    }

    fun imageLoaded(owner: Long) {
        if (!jobs.isActive || state.value.selection?.generation != owner) return
        imageReady = true
        scheduleImage()
    }

    private fun scheduleImage() {
        timer?.cancel()
        val selected = state.value.selection ?: return
        if (!active || !imageReady || !state.value.sequence || selected.media.kind != "image") return
        timer = scope.launch {
            delay(5_000)
            if (state.value.selection?.generation == selected.generation && state.value.sequence && active) navigate(Direction.Next)
        }
    }

    fun videoEnded(owner: Long) {
        if (jobs.isActive && state.value.selection?.generation == owner && active && state.value.sequence && !state.value.selectionLoading) {
            navigate(Direction.Next)
        }
    }

    fun mediaFailed(owner: Long, unauthorized: Boolean = false) {
        if (!jobs.isActive || state.value.selection?.generation != owner) return
        if (unauthorized) { onUnauthorized(); return }
        timer?.cancel()
        onPause()
        mutable.update { it.copy(sequence = false, viewerError = "Cannot load this media. Check the connection or choose another item.") }
    }

    fun mediaAuthExpired() { if (jobs.isActive) onUnauthorized() }

    fun setActive(value: Boolean) {
        active = value
        if (!value) {
            timer?.cancel()
            onPause()
            mutable.update { it.copy(sequence = false) }
        }
    }

    fun closeViewer() {
        beginSelection()
        generation++
        mutable.update { it.copy(viewerOpen = false, selection = null, selectionLoading = false, sequence = false, viewerError = null) }
        onSelection(null)
    }

    fun close() {
        pageRevision++
        viewerRevision++
        jobs.cancel()
        mutable.update { it.copy(selection = null, viewerOpen = false, sequence = false) }
        onSelection(null)
    }

    private fun report(error: Exception, viewer: Boolean) {
        if (error is GalleryFailure && error.status == 401) { onUnauthorized(); return }
        val message = when (error) {
            is GalleryFailure -> error.message
            is IllegalArgumentException -> "This item or server response is unavailable. Refresh the Library."
            else -> "Cannot reach the gallery. Check the connection and retry."
        }
        mutable.update { if (viewer) it.copy(viewerError = message, sequence = false) else it.copy(libraryError = message) }
    }
}
