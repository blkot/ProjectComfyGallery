import SwiftUI

struct MediaGridCell: View {
    let media: XRMediaSummary

    var body: some View {
        ZStack(alignment: .bottomTrailing) {
            AuthenticatedPreviewView(media: media)

            if media.kind == .video {
                Image(systemName: "play.fill")
                    .font(.headline)
                    .padding(10)
                    .background(.regularMaterial, in: Circle())
                    .padding(10)
                    .accessibilityHidden(true)
            }

            VStack(spacing: 8) {
                if media.isTrash {
                    Image(systemName: "trash.fill")
                        .accessibilityLabel("In Trash")
                }
                if media.kind == .video && media.spatialAvailable {
                    Image(
                        systemName: "cube.transparent.fill"
                    )
                    .accessibilityLabel("Spatial video available")
                } else if media.kind != .video && media.prefersSpatialPlayback {
                    Image(systemName: "cube.transparent")
                        .accessibilityLabel("Spatial playback preferred")
                }
            }
            .font(.caption)
            .padding(8)
            .background(.regularMaterial, in: Capsule())
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .padding(8)
            .opacity(
                (
                    media.isTrash
                        || media.spatialAvailable
                        || (media.kind != .video && media.prefersSpatialPlayback)
                ) ? 1 : 0
            )
            .accessibilityHidden(
                !media.isTrash
                    && !media.spatialAvailable
                    && (media.kind == .video || !media.prefersSpatialPlayback)
            )
        }
        .aspectRatio(2.0 / 3.0, contentMode: .fit)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .contentShape(.hoverEffect, RoundedRectangle(cornerRadius: 18, style: .continuous))
        .hoverEffect()
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityLabel)
        .accessibilityHint("Opens the media card")
    }

    private var accessibilityLabel: String {
        var labels = [media.kind == .video ? "Video" : "Image"]
        if media.favorite {
            labels.append("Favorite")
        }
        if media.kind != .video && media.prefersSpatialPlayback {
            labels.append("Spatial playback preferred")
        }
        if media.kind == .video && media.spatialAvailable {
            labels.append("Spatial video available")
        }
        return labels.joined(separator: ", ")
    }
}
