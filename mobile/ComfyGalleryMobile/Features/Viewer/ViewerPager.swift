import SwiftUI

/// A three-page, direction-locked film strip. One drag can commit only one neighbor.
struct ViewerPager<Content: View>: View {
    let pages: [MobileMediaSummary]
    @Binding var selection: String?
    @Binding var isInteracting: Bool
    let isEnabled: Bool
    let policy: ViewerPagingPolicy
    let showDetails: () -> Void
    let close: () -> Void
    @ViewBuilder var content: (MobileMediaSummary, CGSize) -> Content
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @GestureState private var gestureActive = false
    @State private var axis: ViewerPagingPolicy.Axis = .undecided
    @State private var offset: CGFloat = 0
    @State private var settling = false

    var body: some View {
        GeometryReader { geometry in
            ZStack {
                ForEach(Array(pages.enumerated()), id: \.element.id) { index, item in
                    content(item, geometry.size)
                        .frame(width: geometry.size.width, height: geometry.size.height)
                        .offset(x: CGFloat(index - selectedIndex) * geometry.size.width + offset)
                        .allowsHitTesting(item.id == selection && !settling)
                        .accessibilityHidden(item.id != selection)
                }
            }
            .frame(width: geometry.size.width, height: geometry.size.height)
            .clipped()
            .contentShape(.rect)
            .simultaneousGesture(drag(width: geometry.size.width), including: isEnabled ? .all : .subviews)
            .accessibilityAction(named: "上一项") { settle(step: -1, width: geometry.size.width) }
            .accessibilityAction(named: "下一项") { settle(step: 1, width: geometry.size.width) }
            .accessibilityAction(named: "显示媒体详情") { if isEnabled && !settling { showDetails() } }
        }
        .onChange(of: gestureActive) { _, active in
            if !active && !settling { reset() }
        }
        .onChange(of: isEnabled) { _, enabled in
            if !enabled && !settling { reset() }
        }
        .onDisappear { reset() }
    }

    private var selectedIndex: Int { pages.firstIndex { $0.id == selection } ?? 0 }

    private func neighbor(_ step: Int) -> String? {
        let index = selectedIndex + step
        guard step != 0, pages.indices.contains(index) else { return nil }
        return pages[index].id
    }

    private func drag(width: CGFloat) -> some Gesture {
        DragGesture(minimumDistance: policy.intentDistance)
            .updating($gestureActive) { _, state, _ in state = true }
            .onChanged { value in
                guard isEnabled, !settling else { return }
                isInteracting = true
                axis = policy.lockedAxis(axis, translation: value.translation)
                guard axis == .horizontal else { return }
                offset = policy.dragOffset(value.translation.width, width: width,
                                           hasNeighbor: neighbor(value.translation.width < 0 ? 1 : -1) != nil)
            }
            .onEnded { value in
                guard isEnabled, !settling else { return }
                let locked = policy.lockedAxis(axis, translation: value.translation)
                if locked == .horizontal {
                    settle(step: policy.pageStep(axis: locked, translation: value.translation,
                                                 predicted: value.predictedEndTranslation, width: width), width: width)
                } else {
                    reset()
                    switch policy.verticalAction(axis: locked, translation: value.translation) {
                    case .details: showDetails()
                    case .dismiss: close()
                    case .none: break
                    }
                }
            }
    }

    private func settle(step: Int, width: CGFloat) {
        guard isEnabled, !settling else { return }
        let origin = selection
        let target = neighbor(step)
        settling = true
        isInteracting = true
        withAnimation(reduceMotion ? nil : .snappy(duration: 0.22), completionCriteria: .removed) {
            offset = target == nil ? 0 : -CGFloat(step) * width
        } completion: {
            // Rebase the film strip atomically after the snap, never during its animation.
            var transaction = Transaction()
            transaction.disablesAnimations = true
            withTransaction(transaction) {
                if selection == origin, let target { selection = target }
                reset()
            }
        }
    }

    private func reset() {
        offset = 0
        axis = .undecided
        settling = false
        isInteracting = false
    }
}
