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
                if media.spatialViewPreferred {
                    Image(systemName: "cube.transparent")
                        .accessibilityLabel("Spatial")
                }
            }
            .font(.caption)
            .padding(8)
            .background(.regularMaterial, in: Capsule())
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .padding(8)
            .opacity(media.isTrash || media.spatialViewPreferred ? 1 : 0)
            .accessibilityHidden(!media.isTrash && !media.spatialViewPreferred)
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
        if media.spatialViewPreferred {
            labels.append("Spatial")
        }
        return labels.joined(separator: ", ")
    }
}
