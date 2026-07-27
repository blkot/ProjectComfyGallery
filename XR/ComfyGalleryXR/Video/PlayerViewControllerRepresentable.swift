import AVKit
import SwiftUI

struct PlayerViewControllerRepresentable: UIViewControllerRepresentable {
    let player: AVPlayer?

    func makeUIViewController(context: Context) -> AVPlayerViewController {
        let controller = AVPlayerViewController()
        controller.player = player
        controller.showsPlaybackControls = true
        return controller
    }

    func updateUIViewController(_ controller: AVPlayerViewController, context: Context) {
        if controller.player !== player {
            controller.player = player
        }
    }

    static func dismantleUIViewController(
        _ controller: AVPlayerViewController,
        coordinator: Void
    ) {
        controller.player?.pause()
        controller.player = nil
    }
}
