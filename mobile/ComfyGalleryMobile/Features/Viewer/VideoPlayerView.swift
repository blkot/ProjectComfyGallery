import SwiftUI
import AVKit

struct VideoPlayerView: View {
    let videoURL: URL
    let posterImage: UIImage?

    @State private var player: AVPlayer?
    @State private var isMuted = false

    var body: some View {
        Group {
            if let player = player {
                VideoPlayer(player: player)
                    .onAppear {
                        player.isMuted = isMuted
                    }
            } else if let poster = posterImage {
                Image(uiImage: poster)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .overlay {
                        ProgressView()
                            .scaleEffect(1.5)
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                            .background(.ultraThinMaterial)
                    }
            }
        }
        .onAppear {
            player = AVPlayer(url: videoURL)
            player?.isMuted = isMuted
        }
        .onDisappear {
            player?.pause()
            player = nil
        }
        .toolbar {
            ToolbarItem(placement: .bottomBar) {
                Button {
                    isMuted.toggle()
                    player?.isMuted = isMuted
                } label: {
                    Image(systemName: isMuted ? "speaker.slash.fill" : "speaker.wave.2.fill")
                }
            }
        }
    }
}
