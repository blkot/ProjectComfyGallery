package com.comfygallery.quest

import com.comfygallery.quest.scene.PanelLayout
import org.junit.Assert.*
import org.junit.Test

class PanelLayoutTest {
    @Test fun `controls remain below resized media with a constant world gap`() {
        for (scale in listOf(.5f, 1f, 1.5f, 2.5f)) {
            val mediaBottom = -PanelLayout.mediaHeight * scale / 2f
            // Spatial SDK's default TransformParent composes poses, not parent Scale.
            val controlsTop = PanelLayout.controlsOffset(scale) + PanelLayout.controlsHeight / 2f
            assertEquals(.045f, mediaBottom - controlsTop, .0001f)
        }
    }

    @Test fun `portrait and landscape videos fit the frame without aspect distortion`() {
        for ((width, height) in listOf(1080 to 1920, 3840 to 2160, 2400 to 1000)) {
            val (panelWidth, panelHeight) = PanelLayout.videoSize(width, height)
            assertTrue(panelWidth <= PanelLayout.mediaWidth)
            assertTrue(panelHeight <= PanelLayout.mediaHeight)
            assertEquals(width.toFloat() / height, panelWidth / panelHeight, .0001f)
        }
    }
}
