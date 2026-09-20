package com.comfygallery.quest.scene

import com.meta.spatial.core.Pose
import com.meta.spatial.core.Quaternion
import com.meta.spatial.core.Vector3

enum class PositionAction { BringHere, FaceMe, Closer, Farther, Left, Right, Up, Down }

/** One-shot placement relative to the current head pose; panels stay put afterwards. */
object PanelPlacement {
    const val minDistance = .8f
    const val maxDistance = 8f

    fun inFront(head: Pose, distance: Float, side: Float = 0f): Pose {
        val forward = head.forward()
        val horizontal = Vector3(forward.x, 0f, forward.z)
        // Looking straight up/down must not produce NaNs.
        val direction = if (horizontal.length() > .001f) horizontal.normalize() else Vector3(0f, 0f, 1f)
        val right = Vector3(direction.z, 0f, -direction.x)
        val position = head.t + direction * distance.coerceIn(minDistance, maxDistance) + right * side
        return facing(position, head)
    }

    fun adjust(panel: Pose, head: Pose, action: PositionAction, distance: Float): Pose {
        if (action == PositionAction.BringHere) return inFront(head, distance)
        var position = panel.t
        val fromHead = position - head.t
        val length = fromHead.length()
        val direction = if (length > .001f) fromHead * (1f / length) else head.forward()
        val right = head.q * Vector3(1f, 0f, 0f)
        position = when (action) {
            PositionAction.Closer -> head.t + direction * (length - .25f).coerceIn(minDistance, maxDistance)
            PositionAction.Farther -> head.t + direction * (length + .25f).coerceIn(minDistance, maxDistance)
            PositionAction.Left -> position - right * .2f
            PositionAction.Right -> position + right * .2f
            PositionAction.Up -> position + Vector3(0f, .2f, 0f)
            PositionAction.Down -> position - Vector3(0f, .2f, 0f)
            else -> position
        }
        return facing(position, head)
    }

    private fun facing(position: Vector3, head: Pose): Pose {
        val awayFromHead = position - head.t
        // Meta panels present their front on local -Z, so +Z points away from the viewer.
        return Pose(position, if (awayFromHead.length() > .001f) Quaternion.lookRotation(awayFromHead) else head.q)
    }
}
