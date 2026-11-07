import SwiftUI

/// Errors/export status float above the toolbar without resizing the media viewport.
/// Favorite/rating success has no banner: the selected control is the acknowledgement.
struct ViewerStatusOverlay: View {
    let message: String?
    let hasError: Bool
    let permissionDenied: Bool
    let retry: () -> Void

    var body: some View {
        if let message {
            VStack(spacing: 4) {
                Text(message).font(.footnote).multilineTextAlignment(.center)
                if hasError { Button("重试当前页面", action: retry).font(.footnote).frame(minHeight: 44) }
                if permissionDenied, let settings = URL(string: UIApplication.openSettingsURLString) {
                    Link("打开系统设置", destination: settings).font(.footnote).frame(minHeight: 44)
                }
            }
            .padding(12)
            .frame(maxWidth: .infinity)
            .fixedSize(horizontal: false, vertical: true)
            .background(.regularMaterial, in: .rect(cornerRadius: 12))
            .padding(.horizontal, 12)
        }
    }
}
