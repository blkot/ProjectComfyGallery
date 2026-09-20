package com.comfygallery.quest.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import kotlinx.coroutines.launch
import com.comfygallery.quest.ConnectedGallery
import com.comfygallery.quest.data.Direction
import com.comfygallery.quest.library.GalleryStore
import com.comfygallery.quest.media.VideoSession
import com.comfygallery.quest.media.isUnauthorized
import com.comfygallery.quest.scene.PositionAction

private val Ink = Color(0xFF10151E)
private val Surface = Color(0xFF1C2533)

@Composable fun GalleryTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = darkColorScheme(primary = Color(0xFFB5D4FF), background = Ink, surface = Surface), content = content)
}

@Composable private fun Panel(scrollable: Boolean = false, compact: Boolean = false, content: @Composable ColumnScope.() -> Unit) {
    Surface(shape = RoundedCornerShape(28.dp), color = Ink, modifier = Modifier.fillMaxSize()) {
        val padding = if (compact) 12.dp else 24.dp
        val modifier = if (scrollable) Modifier.padding(padding).verticalScroll(rememberScrollState()) else Modifier.padding(padding)
        Column(modifier, verticalArrangement = Arrangement.spacedBy(if (compact) 6.dp else 12.dp), content = content)
    }
}

@Composable fun ConnectPanel(address: String, busy: Boolean, error: String?, hasPrivateDefault: Boolean, usePrivateDefault: () -> Unit, position: (PositionAction) -> Unit, connect: (String, String) -> Unit) {
    var url by remember(address) { mutableStateOf(address) }
    // Deliberately not saveable: the plaintext token must not enter saved-instance state.
    var token by remember { mutableStateOf("") }
    var manualEntry by remember { mutableStateOf(!hasPrivateDefault) }
    Panel {
        Text("ComfyGallery", style = MaterialTheme.typography.headlineLarge)
        Text("Your library, with room to look.", style = MaterialTheme.typography.titleLarge)
        Spacer(Modifier.height(28.dp))
        Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(20.dp)) {
            Text("Connect to your Gallery", style = MaterialTheme.typography.headlineSmall)
            if (hasPrivateDefault) {
                Button(onClick = usePrivateDefault, enabled = !busy, modifier = Modifier.heightIn(min = 52.dp)) { Text("Connect to my Gallery") }
                TextButton(onClick = { manualEntry = !manualEntry }, enabled = !busy) { Text(if (manualEntry) "Hide manual entry" else "Use another connection") }
            }
            if (manualEntry) {
                Text("Use the Gallery server address and an API token created in its web app.")
                OutlinedTextField(url, { url = it }, label = { Text("Gallery URL") }, placeholder = { Text("http://192.168.1.20:8000") },
                    singleLine = true, enabled = !busy, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri), modifier = Modifier.fillMaxWidth())
                OutlinedTextField(token, { token = it }, label = { Text("API token") }, singleLine = true,
                    visualTransformation = PasswordVisualTransformation(), enabled = !busy,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password), modifier = Modifier.fillMaxWidth())
                Button(onClick = { connect(url, token) }, enabled = !busy && url.isNotBlank() && token.isNotBlank(), modifier = Modifier.heightIn(min = 52.dp)) {
                    Text(if (busy) "Connecting…" else "Connect")
                }
            }
            if (error != null) Text(error, color = MaterialTheme.colorScheme.error)
            if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            PositionControls(position)
            Text("For HTTP servers, use a trusted local network. HTTPS keeps the connection encrypted.", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable fun LibraryPanel(profile: ConnectedGallery, disconnect: () -> Unit, reset: () -> Unit, position: (PositionAction) -> Unit) {
    val state by profile.store.state.collectAsState()
    val grid = rememberLazyGridState()
    val actions = rememberCoroutineScope()
    var positioning by remember { mutableStateOf(false) }
    val lastVisible by remember { derivedStateOf { grid.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: -1 } }
    LaunchedEffect(state.scope) { grid.scrollToItem(0) }
    LaunchedEffect(lastVisible, state.page.nextOffset, state.loading, state.libraryError, state.scanPaused) {
        profile.store.viewportChanged(lastVisible)
    }
    Panel(compact = true) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Library", style = MaterialTheme.typography.headlineSmall, modifier = Modifier.weight(1f))
            TextButton(onClick = { profile.store.refresh() }) { Text("Refresh") }
            TextButton(onClick = { positioning = !positioning }) { Text(if (positioning) "Done" else "Position") }
            TextButton(onClick = reset) { Text("Reset layout") }
            TextButton(onClick = disconnect) { Text("Disconnect") }
        }
        if (positioning) PositionControls(position)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            listOf(null to "All", "image" to "Images", "video" to "Videos").forEach { (kind, label) ->
                FilterChip(selected = state.scope.kind == kind, onClick = { profile.store.refresh(state.scope.copy(kind = kind)) }, label = { Text(label) })
            }
            FilterChip(selected = state.scope.favoritesOnly, onClick = { profile.store.refresh(state.scope.copy(favoritesOnly = !state.scope.favoritesOnly)) }, label = { Text("Favorites") })
            Spacer(Modifier.weight(1f))
            TextButton(onClick = { profile.store.refresh(state.scope.copy(oldestFirst = !state.scope.oldestFirst)) }) {
                Text(if (state.scope.oldestFirst) "Oldest first" else "Newest first")
            }
        }
        LazyVerticalGrid(columns = GridCells.Adaptive(136.dp), state = grid, modifier = Modifier.weight(1f),
            horizontalArrangement = Arrangement.spacedBy(10.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(state.page.items, key = { it.id }) { media ->
                var failed by remember(media.id) { mutableStateOf(false) }
                val url = remember(media.previewUrl, profile) { runCatching { profile.connection.resolve(media.previewUrl).toString() }.getOrNull() }
                Card(onClick = { profile.store.open(media.id) }, shape = RoundedCornerShape(10.dp)) {
                    Box(Modifier.fillMaxWidth().aspectRatio(2f / 3f).background(Surface), contentAlignment = Alignment.Center) {
                        if (failed || url == null) Text("Preview unavailable", Modifier.padding(12.dp))
                        else AsyncImage(model = ImageRequest.Builder(LocalContext.current).data(url).size(480, 720).build(),
                            imageLoader = profile.images, contentDescription = "${media.kind}${if (media.favorite) ", favorite" else ""}",
                            contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize(),
                            onError = { failed = true; if (it.result.throwable.isUnauthorized()) profile.store.mediaAuthExpired() })
                        if (media.kind == "video") Text("Video", Modifier.align(Alignment.BottomStart).background(Ink.copy(alpha = .85f)).padding(6.dp))
                        if (media.favorite) Text("★", Modifier.align(Alignment.TopEnd).padding(8.dp), color = MaterialTheme.colorScheme.primary)
                        if (media.spatialAvailable) Text("Spatial variant", Modifier.align(Alignment.BottomEnd).background(Ink.copy(alpha = .85f)).padding(6.dp), style = MaterialTheme.typography.labelSmall)
                    }
                }
            }
            item(span = { GridItemSpan(maxLineSpan) }, key = "paging-status") {
                Column(Modifier.fillMaxWidth().padding(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    when {
                        state.loading -> CircularProgressIndicator(Modifier.size(26.dp))
                        state.libraryError != null -> {
                            Text(state.libraryError!!, color = MaterialTheme.colorScheme.error)
                            TextButton(onClick = profile.store::loadMore) { Text("Retry") }
                        }
                        state.scanPaused -> {
                            Text("No ready items in the last pages.")
                            TextButton(onClick = profile.store::loadMore) { Text("Continue searching") }
                        }
                        state.page.exhausted -> Text(if (state.page.items.isEmpty()) "No ready media in this view." else "End of this view", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("${state.page.items.size} items · scroll for more", modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
            TextButton(onClick = { actions.launch { grid.animateScrollToItem((grid.firstVisibleItemIndex - 12).coerceAtLeast(0)) } }, enabled = grid.canScrollBackward) { Text("Page up") }
            TextButton(onClick = { actions.launch { grid.animateScrollToItem((grid.firstVisibleItemIndex + 12).coerceAtMost((state.page.items.size - 1).coerceAtLeast(0))) } }, enabled = grid.canScrollForward) { Text("Page down") }
        }
    }
}

@Composable fun ImagePanel(profile: ConnectedGallery) {
    val state by profile.store.state.collectAsState()
    val selected = state.selection
    if (selected == null || selected.media.kind != "image") {
        Box(Modifier.fillMaxSize().background(Color.Black), contentAlignment = Alignment.Center) {
            if (state.selectionLoading) CircularProgressIndicator()
            else if (selected == null) Text(state.viewerError ?: "Choose an item in the Library")
        }
        return
    }
    val url = remember(selected.generation, profile) {
        runCatching { profile.connection.resolve(selected.media.originalUrl ?: selected.media.previewUrl).toString() }.getOrNull()
    }
    var loading by remember(selected.generation) { mutableStateOf(true) }
    var failed by remember(selected.generation) { mutableStateOf(false) }
    LaunchedEffect(url, selected.generation) { if (url == null) profile.store.mediaFailed(selected.generation) }
    Surface(color = Color.Black, shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxSize()) {
        Box(contentAlignment = Alignment.Center) {
            if (url == null) Text("Image URL unavailable")
            else AsyncImage(model = ImageRequest.Builder(LocalContext.current).data(url).size(1920, 1152).build(),
                imageLoader = profile.images, contentDescription = "Selected image", contentScale = ContentScale.Fit, modifier = Modifier.fillMaxSize(),
                onSuccess = { loading = false; profile.store.imageLoaded(selected.generation) },
                onError = { loading = false; failed = true; profile.store.mediaFailed(selected.generation, it.result.throwable.isUnauthorized()) })
            if (url != null && loading) CircularProgressIndicator()
            if (failed) Text("Image unavailable · 64 MB transfer limit", Modifier.padding(24.dp))
        }
    }
}

@Composable fun ViewerControls(store: GalleryStore, video: VideoSession, position: (PositionAction) -> Unit, resize: (Float) -> Unit) {
    val state by store.state.collectAsState()
    val playback by video.state.collectAsState()
    val selected = state.selection
    var settings by remember { mutableStateOf(false) }
    var positioning by remember { mutableStateOf(false) }
    LaunchedEffect(state.loop, state.sequence) { video.setLoop(state.loop && !state.sequence) }
    Panel(scrollable = true, compact = true) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(selected?.scope?.label ?: "Viewer", style = MaterialTheme.typography.labelMedium, maxLines = 1, modifier = Modifier.weight(1f))
            if (state.selectionLoading || playback.buffering) CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
            TextButton(onClick = { positioning = !positioning; settings = false }) { Text(if (positioning) "Done" else "Position / Size") }
            TextButton(onClick = { settings = !settings; positioning = false }) { Text(if (settings) "Done" else "Options") }
            TextButton(onClick = store::closeViewer) { Text("Close") }
        }
        if (positioning) {
            PositionControls(position, resize)
        } else if (!settings) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = { store.navigate(Direction.Previous) }, enabled = selected != null && state.inScope && !state.selectionLoading) { Text("Previous") }
                if (selected?.media?.kind == "video") Button(onClick = {
                    if (playback.playing) { video.pause(); store.setSequence(false) } else video.play()
                }, enabled = !state.selectionLoading && state.viewerError == null) { Text(if (playback.playing) "Pause" else "Play") }
                TextButton(onClick = { store.navigate(Direction.Next) }, enabled = selected != null && state.inScope && !state.selectionLoading) { Text("Next") }
                Spacer(Modifier.weight(1f))
                FilterChip(selected = selected?.media?.favorite == true, onClick = store::favorite,
                    enabled = selected != null && !state.favoriteSaving, label = { Text(if (selected?.media?.favorite == true) "★ Favorite" else "Favorite") })
                FilterChip(selected = state.sequence, onClick = {
                    store.setSequence(!state.sequence)
                    if (!state.sequence && selected?.media?.kind == "video") video.play()
                }, enabled = selected != null && state.inScope && state.viewerError == null, label = { Text("Auto Play") })
            }
            if (selected?.media?.kind == "video") {
                var seeking by remember(selected.generation) { mutableStateOf<Float?>(null) }
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(timeLabel(playback.positionMs), style = MaterialTheme.typography.bodySmall)
                    Slider(value = seeking ?: (playback.positionMs.toFloat() / playback.durationMs.coerceAtLeast(1)).coerceIn(0f, 1f),
                        onValueChange = { seeking = it }, onValueChangeFinished = { seeking?.let(video::seek); seeking = null },
                        enabled = playback.durationMs > 0 && !state.selectionLoading, modifier = Modifier.weight(1f))
                    Text(timeLabel(playback.durationMs), style = MaterialTheme.typography.bodySmall)
                    TextButton(onClick = video::mute) { Text(if (playback.muted) "Unmute" else "Mute") }
                }
            }
        } else {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                FilterChip(selected = state.loop, onClick = { store.setLoop(!state.loop) }, label = { Text("Loop video") })
                Text("Volume", style = MaterialTheme.typography.bodySmall)
                Slider(playback.volume, video::volume, modifier = Modifier.weight(1f))
                TextButton(onClick = video::mute) { Text(if (playback.muted) "Unmute" else "Mute") }
            }
            Text(if (state.sequence) "Auto Play advances at video end; your Loop preference is kept." else "Position / Size brings the screen to you and adjusts its size.", style = MaterialTheme.typography.bodySmall)
        }
        (state.viewerError ?: state.notice)?.let { Text(it, color = if (state.viewerError != null) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface, style = MaterialTheme.typography.bodySmall) }
    }
}

@Composable private fun PositionControls(position: (PositionAction) -> Unit, resize: ((Float) -> Unit)? = null) {
    Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        Button(onClick = { position(PositionAction.BringHere) }) { Text("Bring here") }
        TextButton(onClick = { position(PositionAction.FaceMe) }) { Text("Face me") }
        TextButton(onClick = { position(PositionAction.Closer) }) { Text("Closer") }
        TextButton(onClick = { position(PositionAction.Farther) }) { Text("Farther") }
    }
    Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        TextButton(onClick = { position(PositionAction.Left) }) { Text("Left") }
        TextButton(onClick = { position(PositionAction.Right) }) { Text("Right") }
        TextButton(onClick = { position(PositionAction.Up) }) { Text("Up") }
        TextButton(onClick = { position(PositionAction.Down) }) { Text("Down") }
        if (resize != null) {
            TextButton(onClick = { resize(1f / 1.15f) }) { Text("Smaller") }
            TextButton(onClick = { resize(1.15f) }) { Text("Larger") }
        }
    }
    Text("Move: aim at the outer frame and hold the side grip. Resize: drag a corner.", style = MaterialTheme.typography.bodySmall)
}

private fun timeLabel(milliseconds: Long): String {
    val seconds = milliseconds / 1000
    return "%d:%02d".format(seconds / 60, seconds % 60)
}
