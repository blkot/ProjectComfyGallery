import RealityKit
import SwiftUI

struct SpatialImageView: View {
    let controller: SpatialImageController

    var body: some View {
        GeometryReader3D { proxy in
            RealityView { content in
                content.add(controller.entity)
                controller.presentationDidMount()
                fit(using: content, proxy: proxy)
            } update: { content in
                fit(using: content, proxy: proxy)
            }
        }
        .accessibilityLabel("Generated spatial image")
    }

    private func fit(using content: RealityViewContent, proxy: GeometryProxy3D) {
        guard
            let presentationSize = controller
                .entity
                .observable
                .components[ImagePresentationComponent.self]?
                .presentationScreenSize
        else {
            return
        }
        let bounds = content.convert(
            proxy.frame(in: .local),
            from: .local,
            to: .scene
        )
        controller.fit(
            presentationSize: presentationSize,
            availableSize: SIMD2(
                max(0.001, bounds.extents.x),
                max(0.001, bounds.extents.y)
            )
        )
    }
}
