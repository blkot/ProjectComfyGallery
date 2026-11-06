import SwiftUI
import AVKit

struct VideoPlayerView: View {
    let videoURL: URL
    let posterImage: UIImage?
    @Environment(\.scenePhase) private var scenePhase
    @State private var player: AVPlayer?

    var body: some View {
        Group {
            if let player { VideoPlayer(player: player) }
            else if let posterImage { Image(uiImage: posterImage).resizable().scaledToFit() }
            else { ProgressView() }
        }
        .task(id: videoURL) {
            player?.pause()
            player = AVPlayer(url: videoURL)
            // Playback is always user initiated; opening a video never starts sound.
        }
        .onChange(of: scenePhase) { _, phase in
            if phase != .active { player?.pause() }
        }
        .onDisappear {
            player?.pause()
            player?.replaceCurrentItem(with: nil)
            player = nil
        }
    }
}
