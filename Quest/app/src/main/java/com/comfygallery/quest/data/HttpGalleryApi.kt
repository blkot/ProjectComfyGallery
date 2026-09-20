package com.comfygallery.quest.data

import java.io.IOException
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.serialization.json.Json
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

class HttpGalleryApi(val connection: GalleryConnection, val client: OkHttpClient) : GalleryApi {
    private val json = Json { ignoreUnknownKeys = true }

    override suspend fun verify() {
        request("health/live")
        request("api/v1/auth/session")
    }

    override suspend fun page(scope: GalleryScope, offset: Int): MediaPage = json.decodeFromString(
        request("api/v1/media", scope.parameters() + mapOf("offset" to offset.toString(), "limit" to "48")),
    )

    override suspend fun detail(id: String): Media = json.decodeFromString(request("api/v1/media/${safeId(id)}"))

    override suspend fun navigation(id: String, scope: GalleryScope): Navigation = json.decodeFromString(
        request("api/v1/media/${safeId(id)}/navigation", scope.parameters()),
    )

    override suspend fun favorite(id: String, value: Boolean) {
        request("api/v1/media/${safeId(id)}/favorite", body = "{\"favorite\":$value}")
    }

    private fun safeId(id: String): String {
        require(id.matches(Regex("[a-zA-Z0-9-]+"))) { "Invalid media identity." }
        return id
    }

    private suspend fun request(path: String, parameters: Map<String, String> = emptyMap(), body: String? = null): String {
        val url = connection.resolve(path).newBuilder().apply {
            parameters.forEach { (key, value) -> addQueryParameter(key, value) }
        }.build()
        val request = Request.Builder().url(url).apply {
            body?.let { put(it.toRequestBody("application/json".toMediaType())) }
        }.build()
        return client.newCall(request).awaitBody()
    }
}

private suspend fun Call.awaitBody(): String = suspendCancellableCoroutine { continuation ->
    continuation.invokeOnCancellation { cancel() }
    enqueue(object : Callback {
        override fun onFailure(call: Call, e: IOException) {
            if (continuation.isActive) continuation.resumeWithException(IOException("Cannot reach the gallery. Check the connection.", e))
        }

        override fun onResponse(call: Call, response: Response) {
            response.use {
                try {
                    if (!it.isSuccessful) throw GalleryFailure(it.code, "HTTP_${it.code}", when (it.code) {
                        401 -> "API token rejected. Reconnect to the gallery."
                        403 -> "The gallery denied this request."
                        404 -> "This item is no longer in the selected view."
                        in 300..399 -> "The server redirected this request. Use its final gallery URL."
                        else -> "The gallery returned HTTP ${it.code}. Try again."
                    })
                    val source = it.body?.source() ?: throw IOException("The gallery returned an empty response.")
                    val buffer = okio.Buffer()
                    while (!source.exhausted()) {
                        if (!continuation.isActive) return
                        val count = source.read(buffer, 8192)
                        if (count < 0) break
                        if (buffer.size > 4L * 1024 * 1024) throw IOException("The gallery response is too large.")
                    }
                    if (continuation.isActive) continuation.resume(buffer.readUtf8())
                } catch (e: Exception) {
                    if (continuation.isActive) continuation.resumeWithException(e)
                }
            }
        }
    })
}
