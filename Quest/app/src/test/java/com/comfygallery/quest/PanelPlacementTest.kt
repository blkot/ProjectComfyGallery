package com.comfygallery.quest

import com.comfygallery.quest.scene.PanelPlacement
import com.comfygallery.quest.scene.PositionAction
import com.meta.spatial.core.Pose
import com.meta.spatial.core.Quaternion
import com.meta.spatial.core.Vector3
import org.junit.Assert.*
import org.junit.Test

class PanelPlacementTest {
    @Test fun `bring here follows translated and turned head instead of world z`() {
        for (yaw in listOf(0f, 90f, 180f, -90f)) {
            val head = Pose(Vector3(4f, 1.2f, -3f), Quaternion(0f, yaw, 0f))
            val panel = PanelPlacement.inFront(head, 2f)
            assertVector(head.t + head.forward() * 2f, panel.t)
            assertVector((panel.t - head.t).normalize(), panel.forward())
            assertVector(Vector3(4f, 1.2f, -3f), head.t)
        }
    }

    @Test fun `side panels face the viewer and face me preserves position`() {
        val head = Pose(Vector3(2f, 1.3f, 5f), Quaternion(0f, 90f, 0f))
        for (side in listOf(-1.3f, 1.3f)) {
            val placed = PanelPlacement.inFront(head, 2.4f, side)
            assertVector((placed.t - head.t).normalize(), placed.forward())
            val turned = Pose(placed.t, Quaternion())
            val faced = PanelPlacement.adjust(turned, head, PositionAction.FaceMe, 2.4f)
            assertVector(turned.t, faced.t)
            assertVector(placed.forward(), faced.forward())
        }
    }

    @Test fun `closer and farther stay on the same ray with bounded distance`() {
        val head = Pose(Vector3(2f, 1.3f, 5f))
        var panel = PanelPlacement.inFront(head, 2.4f, 1.3f)
        val direction = (panel.t - head.t).normalize()
        repeat(100) { panel = PanelPlacement.adjust(panel, head, PositionAction.Closer, 2.4f) }
        assertEquals(PanelPlacement.minDistance, (panel.t - head.t).length(), .0001f)
        assertVector(direction, (panel.t - head.t).normalize())
        repeat(100) { panel = PanelPlacement.adjust(panel, head, PositionAction.Farther, 2.4f) }
        assertEquals(PanelPlacement.maxDistance, (panel.t - head.t).length(), .0001f)
        assertVector(direction, panel.forward())
    }

    @Test fun `straight up gaze and coincident positions have finite placement`() {
        val head = Pose(Vector3(2f, 1.3f, 5f), Quaternion(90f, 0f, 0f))
        val panel = PanelPlacement.inFront(head, 2f)
        assertEquals(head.t.y, panel.t.y, .0001f)
        assertEquals(2f, (panel.t - head.t).length(), .0001f)
        val moved = PanelPlacement.adjust(head, head, PositionAction.Closer, 2f)
        assertEquals(PanelPlacement.minDistance, (moved.t - head.t).length(), .0001f)
        assertTrue(moved.forward().x.isFinite())
    }

    private fun assertVector(expected: Vector3, actual: Vector3) {
        assertEquals(expected.x, actual.x, .0001f)
        assertEquals(expected.y, actual.y, .0001f)
        assertEquals(expected.z, actual.z, .0001f)
    }
}
