import simd

enum ImagePresentationScaler {
    static func scale(
        presentationSize: SIMD2<Float>,
        availableSize: SIMD2<Float>
    ) -> SIMD3<Float> {
        guard
            presentationSize.x > 0,
            presentationSize.y > 0,
            availableSize.x > 0,
            availableSize.y > 0
        else {
            return SIMD3(repeating: 1)
        }
        let uniform = min(
            availableSize.x / presentationSize.x,
            availableSize.y / presentationSize.y
        )
        // ImagePresentationComponent owns the generated scene's depth. Scaling Z
        // can flatten or move that geometry outside its intended presentation mesh.
        return SIMD3(uniform, uniform, 1)
    }
}
