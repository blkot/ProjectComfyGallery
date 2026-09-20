package com.comfygallery.quest.scene

/** Meter-based sizes; the controls retain their world size when the media is resized. */
object PanelLayout {
    const val libraryWidth = 1.8f
    const val libraryHeight = 1.65f
    const val mediaWidth = 2.8f
    const val mediaHeight = 1.68f
    const val controlsWidth = 1.9f
    const val controlsHeight = 0.34f

    // TransformParent inherits pose only with TickTransformSystem.applyScale=false.
    fun controlsOffset(scaleY: Float): Float =
        -mediaHeight * scaleY / 2f - controlsHeight / 2f - 0.045f

    fun videoSize(width: Int?, height: Int?): Pair<Float, Float> {
        val ratio = if ((width ?: 0) > 0 && (height ?: 0) > 0) width!!.toFloat() / height!! else 16f / 9f
        return if (ratio >= mediaWidth / mediaHeight) mediaWidth to mediaWidth / ratio else mediaHeight * ratio to mediaHeight
    }
}
