package com.comfygallery.quest

import android.os.Bundle
import androidx.compose.runtime.*
import androidx.compose.ui.platform.ComposeView
import coil.ImageLoader
import coil.memory.MemoryCache
import com.comfygallery.quest.data.*
import com.comfygallery.quest.library.GalleryStore
import com.comfygallery.quest.library.Selection
import com.comfygallery.quest.media.VideoSession
import com.comfygallery.quest.scene.PanelLayout
import com.comfygallery.quest.scene.PanelPlacement
import com.comfygallery.quest.scene.PositionAction
import com.comfygallery.quest.ui.*
import com.meta.spatial.compose.ComposeFeature
import com.meta.spatial.compose.ComposeViewPanelRegistration
import com.meta.spatial.core.*
import com.meta.spatial.isdk.*
import com.meta.spatial.runtime.ReferenceSpace
import com.meta.spatial.runtime.SessionState
import com.meta.spatial.runtime.StereoMode
import com.meta.spatial.toolkit.*
import com.meta.spatial.vr.LocomotionSystem
import com.meta.spatial.vr.VRFeature
import kotlinx.coroutines.*
import okhttp3.OkHttpClient
import okhttp3.Dispatcher

class ConnectedGallery(
    val connection: GalleryConnection,
    val client: OkHttpClient,
    val images: ImageLoader,
    val store: GalleryStore,
)

class QuestActivity : AppSystemActivity() {
    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val credentials by lazy { CredentialStore(this) }
    private val video by lazy { VideoSession(this, appScope,
        onEnded = { profile?.store?.videoEnded(it) },
        onFailed = { owner, auth -> profile?.store?.mediaFailed(owner, auth) }) }
    private var profile by mutableStateOf<ConnectedGallery?>(null)
    private var connecting by mutableStateOf(false)
    private var connectionError by mutableStateOf<String?>(null)
    private var savedAddress by mutableStateOf("")
    private var connectJob: Job? = null
    private var connectRevision = 0L
    private var focused = false
    private var sceneReady = false
    private var library: Entity? = null
    private var viewerRoot: Entity? = null
    private var controls: Entity? = null
    private var videoEntity: Entity? = null
    private var videoPanelId: Int? = null
    private var nextPanelId = 1_500_000
    private var initialPlacementPending = true

    override fun registerFeatures(): List<SpatialFeature> = listOf(VRFeature(this), ComposeFeature())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        systemManager.findSystem<LocomotionSystem>().enableLocomotion(false)
        // Pose parenting only: each video/controls entity owns its physical scale.
        systemManager.findSystem<TickTransformSystem>().applyScale = false
        savedAddress = credentials.address.ifBlank { BuildConfig.GALLERY_URL }
        connectJob = appScope.launch {
            val token = withContext(Dispatchers.IO) { credentials.token() }
            if (token != null && profile == null) connect(savedAddress, token)
        }
    }

    override fun onSceneReady() {
        super.onSceneReady()
        scene.setReferenceSpace(ReferenceSpace.LOCAL_FLOOR)
        scene.enablePassthrough(true)
        scene.setViewOrigin(0f, 0f, 0f, 0f)
        library = movablePanel(R.id.library_panel, libraryPose(),
            PanelLayout.libraryWidth, PanelLayout.libraryHeight, relayout = true)
        // The media frame owns placement and size. Parent pose does not inherit Scale.
        viewerRoot = movablePanel(R.id.image_panel, viewerPose(),
            PanelLayout.mediaWidth, PanelLayout.mediaHeight, relayout = false).apply { setComponent(Visible(false)) }
        controls = Entity.create(Panel(R.id.viewer_panel),
            Transform(Pose(Vector3(0f, PanelLayout.controlsOffset(1f), -0.01f))),
            TransformParent(viewerRoot!!), Scale(Vector3(1f)), Visible(false))
        systemManager.registerSystem(object : SystemBase() {
            private var previous: Vector3? = null
            override fun execute() {
                if (initialPlacementPending && focused && headPose() != null) {
                    initialPlacementPending = false
                    resetLayout()
                }
                val scale = viewerRoot?.tryGetComponent<Scale>()?.scale ?: return
                if (scale == previous) return
                previous = Vector3(scale.x, scale.y, scale.z)
                videoEntity?.setComponent(Scale(Vector3(scale.x, scale.y, 1f)))
                controls?.setComponent(Transform(Pose(Vector3(0f, PanelLayout.controlsOffset(scale.y), -0.01f))))
            }
        })
        sceneReady = true
        showSelection(profile?.store?.state?.value?.selection)
    }

    override fun registerPanels(): List<PanelRegistration> = listOf(
        composePanel(R.id.library_panel, PanelLayout.libraryWidth, PanelLayout.libraryHeight) {
            GalleryTheme {
                val current = profile
                if (current == null) ConnectPanel(savedAddress, connecting, connectionError,
                    hasPrivateDefault = hasPrivateDefault(), usePrivateDefault = ::connectPrivateDefault,
                    position = { positionPanel(library, it, 1.8f) }, connect = ::connect)
                else LibraryPanel(current, { disconnect() }, ::resetLayout) { positionPanel(library, it, 1.8f) }
            }
        },
        composePanel(R.id.viewer_panel, PanelLayout.controlsWidth, PanelLayout.controlsHeight, dpPerMeter = 600f) {
            GalleryTheme { profile?.let { ViewerControls(it.store, video,
                position = { action -> positionPanel(viewerRoot, action, 2.4f) }, resize = ::resizeViewer) } }
        },
        composePanel(R.id.image_panel, PanelLayout.mediaWidth, PanelLayout.mediaHeight) {
            GalleryTheme { profile?.let { ImagePanel(it) } }
        },
    )

    private fun composePanel(id: Int, width: Float, height: Float, dpPerMeter: Float = 500f, content: @Composable () -> Unit) =
        ComposeViewPanelRegistration(id,
            composeViewCreator = { _, context -> ComposeView(context).apply { setContent(content = content) } },
            settingsCreator = { UIPanelSettings(shape = QuadShapeOptions(width, height),
                display = DpPerMeterDisplayOptions(dpPerMeter = dpPerMeter), style = PanelStyleOptions(R.style.PanelTheme)) })

    private fun movablePanel(id: Int, pose: Pose, width: Float, height: Float, relayout: Boolean) = Entity.create(
        Panel(id), Transform(pose), Scale(Vector3(1f)), PanelDimensions(Vector2(width, height)),
        IsdkGrabbable(movementType = IsdkGrabMovementType.Billboard),
        // Keep the grab frame outside and in front of the video surface.
        IsdkPanelGrabHandle(grabHandleCollisionWidths = Vector4(.10f, .10f, .10f, .10f),
            outset = Vector4(.06f, .06f, .06f, .06f), zOffset = -.035f),
        IsdkPanelResize(resizeMode = if (relayout) ResizeMode.Relayout else ResizeMode.Simple,
            minDimensions = Vector2(if (relayout) 1.2f else width * .5f, height * .5f),
            maxDimensions = Vector2(width * 2.5f, height * 2.5f), preserveAspectRatio = !relayout),
    )

    private fun hasPrivateDefault() = BuildConfig.GALLERY_URL.isNotBlank() && BuildConfig.GALLERY_TOKEN.isNotBlank()

    private fun connectPrivateDefault() {
        if (hasPrivateDefault()) connect(BuildConfig.GALLERY_URL, BuildConfig.GALLERY_TOKEN)
    }

    private fun connect(address: String, token: String) {
        connectJob?.cancel()
        val revision = ++connectRevision
        connecting = true
        connectionError = null
        connectJob = appScope.launch {
            var client: OkHttpClient? = null
            try {
                val connection = GalleryConnection(address, token)
                client = connection.client()
                val api = HttpGalleryApi(connection, client)
                api.verify()
                ensureActive()
                if (revision != connectRevision) return@launch
                val encrypted = withContext(Dispatchers.IO) { credentials.encrypt(token.trim()) }
                ensureActive()
                if (revision != connectRevision) return@launch
                credentials.save(connection.base.toString(), encrypted)
                val images = ImageLoader.Builder(this@QuestActivity)
                    .okHttpClient(client.boundedImages().newBuilder()
                        .dispatcher(Dispatcher().apply { maxRequests = 4; maxRequestsPerHost = 2 }).build())
                    .memoryCache { MemoryCache.Builder(this@QuestActivity).maxSizeBytes(64 * 1024 * 1024).build() }
                    .diskCache(null).build()
                val store = GalleryStore(api, appScope, ::showSelection, video::pause) {
                    disconnect("API token expired or was rejected. Reconnect to the gallery.")
                }
                profile = ConnectedGallery(connection, client, images, store)
                savedAddress = connection.base.toString()
                store.setActive(focused)
                store.refresh()
            } catch (e: Exception) {
                client?.dispatcher?.cancelAll()
                client?.connectionPool?.evictAll()
                if (e is CancellationException) throw e
                if (revision == connectRevision) connectionError = when (e) {
                    is GalleryFailure -> e.message
                    is IllegalArgumentException -> "Enter a full http:// or https:// gallery URL and a valid API token."
                    else -> "Connection failed. Check the server address, network, and API token."
                }
            } finally { if (revision == connectRevision) connecting = false }
        }
    }

    private fun disconnect(message: String? = null) {
        connectRevision++
        connectJob?.cancel()
        connecting = false
        val old = profile
        profile = null
        old?.store?.close()
        old?.images?.shutdown()
        old?.client?.dispatcher?.cancelAll()
        old?.client?.connectionPool?.evictAll()
        credentials.clear()
        showSelection(null)
        connectionError = message
    }

    private fun showSelection(selection: Selection?) {
        video.release()
        destroyVideoPanel()
        if (!sceneReady) return
        val isOpen = profile?.store?.state?.value?.viewerOpen == true
        controls?.setComponent(Visible(isOpen))
        viewerRoot?.setComponent(Visible(isOpen))
        if (selection?.media?.kind != "video") return
        val current = profile ?: return
        video.setLoop(current.store.state.value.loop && !current.store.state.value.sequence)
        video.load(selection, current.connection, current.client)
        val dimensions = PanelLayout.videoSize(selection.media.width, selection.media.height)
        val id = ++nextPanelId
        videoPanelId = id
        registerPanel(VideoSurfacePanelRegistration(id,
            surfaceConsumer = { _, surface -> runOnUiThread {
                if (profile === current && videoPanelId == id) video.attach(selection.generation, surface)
            } },
            settingsCreator = { MediaPanelSettings(
                shape = QuadShapeOptions(dimensions.first, dimensions.second),
                display = PixelDisplayOptions(width = (dimensions.first / PanelLayout.mediaWidth * 2560).toInt().coerceAtLeast(1),
                    height = (dimensions.second / PanelLayout.mediaWidth * 2560).toInt().coerceAtLeast(1)),
                rendering = MediaPanelRenderOptions(stereoMode = StereoMode.None),
                style = PanelStyleOptions(R.style.PanelTheme)) }))
        val scale = viewerRoot!!.getComponent<Scale>().scale
        videoEntity = Entity.create(Panel(id), Transform(Pose(Vector3(0f, 0f, -0.012f))),
            TransformParent(viewerRoot!!), Scale(Vector3(scale.x, scale.y, 1f)))
    }

    private fun destroyVideoPanel() {
        videoEntity?.destroy()
        videoEntity = null
        videoPanelId?.let { id ->
            // Same cleanup as Meta's PremiumMediaSample: release registration closures as well.
            panelRegistrations.remove(id)
            systemManager.findSystem<PanelCreationSystem>().panelCreator.remove(id)
        }
        videoPanelId = null
    }

    private fun libraryPose() = Pose(Vector3(-1.30f, 1.45f, 2.4f))
    private fun viewerPose() = Pose(Vector3(1.30f, 1.55f, 2.7f))
    private fun headPose(): Pose? = Query.where { has(AvatarAttachment.id) }
        .filter { isLocal() and by(AvatarAttachment.typeData).isEqualTo("head") }
        .eval().firstOrNull()?.tryGetComponent<Transform>()?.transform

    private fun positionPanel(entity: Entity?, action: PositionAction, distance: Float) {
        val head = headPose() ?: return
        val current = entity?.tryGetComponent<Transform>()?.transform ?: return
        entity.setComponent(Transform(PanelPlacement.adjust(current, head, action, distance)))
    }

    private fun resizeViewer(factor: Float) {
        val entity = viewerRoot ?: return
        val current = entity.getComponent<Scale>().scale.x
        val scale = (current * factor).coerceIn(.5f, 2.5f)
        entity.setComponent(Scale(Vector3(scale, scale, 1f)))
    }

    private fun resetLayout() {
        val head = headPose() ?: return
        library?.setComponent(Transform(PanelPlacement.inFront(head, 2.4f, -1.3f)))
        viewerRoot?.setComponent(Transform(PanelPlacement.inFront(head, 2.7f, 1.3f)))
        library?.setComponent(Scale(Vector3(1f)))
        viewerRoot?.setComponent(Scale(Vector3(1f)))
    }

    override fun onSessionStateChanged(state: SessionState) {
        super.onSessionStateChanged(state)
        focused = state == SessionState.FOCUSED
        video.setFocused(focused)
        profile?.store?.setActive(focused)
    }
    override fun onPause() {
        focused = false
        video.setFocused(false)
        profile?.store?.setActive(false)
        super.onPause()
    }
    override fun onDestroy() {
        profile?.store?.close()
        profile?.images?.shutdown()
        profile?.client?.dispatcher?.cancelAll()
        video.close()
        appScope.cancel()
        super.onDestroy()
    }
}
