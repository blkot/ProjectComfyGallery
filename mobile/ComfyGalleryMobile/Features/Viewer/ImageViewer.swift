import SwiftUI

struct ImageViewer: View {
    let image: UIImage
    @Binding var scale: CGFloat
    @State private var lastScale: CGFloat = 1.0
    @State private var offset: CGSize = .zero
    @State private var lastOffset: CGSize = .zero

    init(image: UIImage, scale: Binding<CGFloat> = .constant(1.0)) {
        self.image = image
        self._scale = scale
    }

    var body: some View {
        Image(uiImage: image)
            .resizable()
            .aspectRatio(contentMode: .fit)
            .scaleEffect(scale)
            .offset(offset)
            .gesture(zoomGesture)
            .simultaneousGesture(panGesture)
            .onTapGesture(count: 2) {
                withAnimation(.spring()) {
                    resetZoom()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .clipped()
    }

    private var zoomGesture: some Gesture {
        MagnifyGesture()
            .onChanged { value in
                let m = value.magnification
                let delta = m / lastScale
                lastScale = m
                scale = min(max(scale * delta, 1), 5)
            }
            .onEnded { _ in
                lastScale = 1.0
                if scale <= 1.05 {
                    withAnimation(.spring()) { resetZoom() }
                }
            }
    }

    private var panGesture: some Gesture {
        DragGesture()
            .onChanged { value in
                guard scale > 1.0 else { return }
                offset = CGSize(
                    width: lastOffset.width + value.translation.width,
                    height: lastOffset.height + value.translation.height
                )
            }
            .onEnded { _ in
                guard scale > 1.0 else { return }
                lastOffset = offset
            }
    }

    private func resetZoom() {
        scale = 1.0
        offset = .zero
        lastOffset = .zero
    }
}
