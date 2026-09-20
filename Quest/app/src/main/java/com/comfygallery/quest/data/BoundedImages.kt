package com.comfygallery.quest.data

import java.io.IOException
import okhttp3.OkHttpClient
import okhttp3.ResponseBody
import okio.ForwardingSource
import okio.Buffer
import okio.buffer

/** Large originals fail recoverably instead of consuming unlimited image memory/network bytes. */
fun OkHttpClient.boundedImages(maxBytes: Long = 64L * 1024 * 1024): OkHttpClient = newBuilder()
    .addInterceptor { chain ->
        val response = chain.proceed(chain.request())
        val body = response.body ?: return@addInterceptor response
        if (body.contentLength() > maxBytes) {
            response.close()
            throw IOException("Image exceeds the display transfer limit.")
        }
        val source = object : ForwardingSource(body.source()) {
            var readBytes = 0L
            override fun read(sink: Buffer, byteCount: Long): Long {
                val count = super.read(sink, byteCount)
                if (count > 0) readBytes += count
                if (readBytes > maxBytes) throw IOException("Image exceeds the display transfer limit.")
                return count
            }
        }.buffer()
        response.newBuilder().body(object : ResponseBody() {
            override fun contentType() = body.contentType()
            override fun contentLength() = body.contentLength()
            override fun source() = source
        }).build()
    }.build()
