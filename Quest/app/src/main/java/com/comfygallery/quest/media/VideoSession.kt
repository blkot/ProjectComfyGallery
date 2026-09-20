package com.comfygallery.quest.media

import android.content.Context
import android.view.Surface
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.PlaybackException
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.datasource.HttpDataSource
import androidx.media3.datasource.okhttp.OkHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import com.comfygallery.quest.data.GalleryConnection
import com.comfygallery.quest.library.Selection
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import okhttp3.OkHttpClient

data class VideoState(
    val playing: Boolean = false,
    val buffering: Boolean = false,
    val positionMs: Long = 0,
    val durationMs: Long = 0,
    val volume: Float = 0.7f,
    val muted: Boolean = false,
)

/** Exactly one decoder. Late listeners and surface callbacks must match its selection owner. */
@androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)
class VideoSession(
    private val context: Context,
    scope: CoroutineScope,
    private val onEnded: (Long) -> Unit,
    private val onFailed: (Long, Boolean) -> Unit,
) {
    private var player: ExoPlayer? = null
    private var owner: Long? = null
    private var playIntent = false
    private var focused = false
    private var attached = false
    private var loop = true
    private val mutable = MutableStateFlow(VideoState())
    val state = mutable.asStateFlow()
    private val clock = scope.launch {
        while (isActive) {
            player?.let { current ->
                mutable.update { it.copy(positionMs = current.currentPosition.coerceAtLeast(0), durationMs = current.duration.coerceAtLeast(0)) }
            }
            delay(250)
        }
    }

    fun load(selection: Selection, connection: GalleryConnection, client: OkHttpClient) {
        release()
        owner = selection.generation
        val url = try { connection.resolve(requireNotNull(selection.media.playbackUrl)).toString() }
        catch (_: Exception) { onFailed(selection.generation, false); return }
        val current = ExoPlayer.Builder(context)
            .setMediaSourceFactory(DefaultMediaSourceFactory(OkHttpDataSource.Factory(client)))
            .build()
        player = current
        playIntent = focused
        current.setAudioAttributes(AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MOVIE).build(), true)
        current.setHandleAudioBecomingNoisy(true)
        current.repeatMode = if (loop) Player.REPEAT_MODE_ONE else Player.REPEAT_MODE_OFF
        current.volume = if (state.value.muted) 0f else state.value.volume
        current.addListener(object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                if (player === current) mutable.update { it.copy(playing = isPlaying) }
            }
            override fun onPlaybackStateChanged(playbackState: Int) {
                if (player !== current) return
                mutable.update { it.copy(buffering = playbackState == Player.STATE_BUFFERING) }
                if (playbackState == Player.STATE_ENDED) onEnded(selection.generation)
            }
            override fun onPlayerError(error: PlaybackException) {
                if (player === current) onFailed(selection.generation, error.isUnauthorized())
            }
        })
        current.setMediaItem(MediaItem.fromUri(url))
        current.prepare()
    }

    fun attach(generation: Long, surface: Surface) {
        if (owner != generation) return
        attached = true
        player?.setVideoSurface(surface)
        player?.playWhenReady = playIntent && focused
    }

    fun play() {
        if (!focused) return
        playIntent = true
        player?.let { if (it.playbackState == Player.STATE_ENDED) it.seekTo(0); it.playWhenReady = attached }
    }
    fun pause() { playIntent = false; player?.pause() }
    fun setFocused(value: Boolean) { focused = value; if (!value) pause() }
    fun setLoop(value: Boolean) { loop = value; player?.repeatMode = if (value) Player.REPEAT_MODE_ONE else Player.REPEAT_MODE_OFF }
    fun seek(fraction: Float) { player?.let { if (it.duration > 0) it.seekTo((it.duration * fraction.coerceIn(0f, 1f)).toLong()) } }
    fun volume(value: Float) {
        mutable.update { it.copy(volume = value.coerceIn(0f, 1f), muted = false) }
        player?.volume = state.value.volume
    }
    fun mute() {
        mutable.update { it.copy(muted = !it.muted) }
        player?.volume = if (state.value.muted) 0f else state.value.volume
    }
    fun release() {
        owner = null
        playIntent = false
        attached = false
        val old = player
        player = null
        old?.clearVideoSurface()
        old?.release()
        mutable.update { VideoState(volume = it.volume, muted = it.muted) }
    }
    fun close() { release(); clock.cancel() }
}

@androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)
fun Throwable.isUnauthorized(): Boolean {
    var current: Throwable? = this
    repeat(12) {
        if ((current as? HttpDataSource.InvalidResponseCodeException)?.responseCode == 401) return true
        if ((current as? coil.network.HttpException)?.response?.code == 401) return true
        current = current?.cause
    }
    return false
}
