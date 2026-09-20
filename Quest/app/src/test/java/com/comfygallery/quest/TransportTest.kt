package com.comfygallery.quest

import com.comfygallery.quest.data.*
import kotlinx.coroutines.runBlocking
import okhttp3.Request
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException
import java.util.concurrent.TimeUnit

class TransportTest {
    @Test fun `prefix survives both backend and already prefixed URLs`() {
        val connection = GalleryConnection("https://gallery.example/nested/gallery", "test-only")
        assertEquals("https://gallery.example/nested/gallery/api/v1/media", connection.resolve("/api/v1/media").toString())
        assertEquals("https://gallery.example/nested/gallery/files/test", connection.resolve("/nested/gallery/files/test").toString())
        assertEquals("https://gallery.example/nested/gallery/files/test", connection.resolve("files/test").toString())
        assertFalse(connection.toString().contains("test-only"))
    }

    @Test fun `reject cross origin credentials port changes and prefix escapes`() {
        val connection = GalleryConnection("https://gallery.example/gallery", "test-only")
        listOf("//evil.example/file", "https://evil.example/file", "http://gallery.example/gallery/file",
            "https://gallery.example:8443/gallery/file", "https://user:pass@gallery.example/gallery/file",
            "../private", "%2e%2e/private", "https://gallery.example/gallery-other/file").forEach { path ->
            assertThrows("accepted $path", IllegalArgumentException::class.java) { connection.resolve(path) }
        }
    }

    @Test fun `authenticate JSON and ranged media without following redirects`() = runBlocking {
        MockWebServer().use { server -> MockWebServer().use { destination ->
            server.enqueue(MockResponse().setBody("{\"status\":\"ok\"}"))
            server.enqueue(MockResponse().setBody("{\"authenticated\":true}"))
            val connection = GalleryConnection(server.url("/gallery/").toString(), "test-token")
            val client = connection.client()
            HttpGalleryApi(connection, client).verify()
            listOf("/gallery/health/live", "/gallery/api/v1/auth/session").forEach { path ->
                val request = server.takeRequest(2, TimeUnit.SECONDS)!!
                assertEquals(path, request.path)
                assertEquals("Bearer test-token", request.getHeader("Authorization"))
            }
            server.enqueue(MockResponse().setResponseCode(206).setHeader("Content-Range", "bytes 0-3/10").setBody("test"))
            client.newCall(Request.Builder().url(connection.resolve("media/file")).header("Range", "bytes=0-3").build()).execute().use {
                assertEquals(206, it.code)
                assertEquals("test", it.body!!.string())
            }
            val rangeRequest = server.takeRequest(2, TimeUnit.SECONDS)!!
            assertEquals("bytes=0-3", rangeRequest.getHeader("Range"))
            assertEquals("Bearer test-token", rangeRequest.getHeader("Authorization"))
            server.enqueue(MockResponse().setResponseCode(302).setHeader("Location", destination.url("/stolen")))
            client.newCall(Request.Builder().url(connection.resolve("media/redirect")).build()).execute().use { assertEquals(302, it.code) }
            assertEquals(0, destination.requestCount)
        } }
    }

    @Test fun `decode additive fields and retain raw pagination contract`() = runBlocking {
        MockWebServer().use { server ->
            server.enqueue(MockResponse().setBody("""{"items":[{"id":"one","kind":"image","status":"ready_with_warnings","preview_url":"/preview/one","favorite":true,"width":null,"future_field":{"x":1}}],"total":70,"limit":48,"offset":48,"future":true}"""))
            val connection = GalleryConnection(server.url("/").toString(), "test-token")
            val result = HttpGalleryApi(connection, connection.client()).page(GalleryScope(favoritesOnly = true), 48)
            assertEquals(48, result.offset)
            assertTrue(result.items.single().playable)
            val request = server.takeRequest(2, TimeUnit.SECONDS)!!
            assertEquals("false", request.requestUrl!!.queryParameter("trash"))
            assertEquals("true", request.requestUrl!!.queryParameter("favorite"))
            assertEquals("48", request.requestUrl!!.queryParameter("offset"))
        }
    }

    @Test fun `401 produces a sanitized connection error`() = runBlocking {
        MockWebServer().use { server ->
            server.enqueue(MockResponse().setResponseCode(401).setBody("private response and test-token"))
            val connection = GalleryConnection(server.url("/").toString(), "test-token")
            try { HttpGalleryApi(connection, connection.client()).verify(); fail("expected 401") }
            catch (error: GalleryFailure) { assertEquals(401, error.status); assertFalse(error.message!!.contains("test-token")) }
        }
    }

    @Test fun `image byte cap covers known and chunked content lengths`() {
        MockWebServer().use { server ->
            val connection = GalleryConnection(server.url("/").toString(), "test-token")
            val client = connection.client().boundedImages(8)
            listOf(MockResponse().setBody("0123456789"), MockResponse().setChunkedBody("0123456789", 3)).forEach { response ->
                server.enqueue(response)
                assertThrows(IOException::class.java) {
                    client.newCall(Request.Builder().url(connection.resolve("image")).build()).execute().use { it.body!!.string() }
                }
            }
        }
    }
}
