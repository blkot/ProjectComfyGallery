import SwiftUI

struct ConflictSheet: View {
    let message: String
    let serverValue: String
    let localValue: String
    let onResolve: (Bool) -> Void

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 40)).foregroundStyle(.orange)
                Text("This score changed elsewhere").font(.headline)
                Text(message).font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)

                VStack(spacing: 8) {
                    HStack { Text("Server value:"); Spacer(); Text(serverValue).fontWeight(.medium) }
                    HStack { Text("Your value:"); Spacer(); Text(localValue).fontWeight(.medium) }
                }
                .padding().background(Color(.secondarySystemBackground)).clipShape(RoundedRectangle(cornerRadius: 12))

                VStack(spacing: 12) {
                    Button { onResolve(true) } label: {
                        Text("Use Server Value").frame(maxWidth: .infinity)
                    }.buttonStyle(.borderedProminent)
                    Button { onResolve(false) } label: {
                        Text("Reapply My Value").frame(maxWidth: .infinity)
                    }.buttonStyle(.bordered)
                }
            }
            .padding()
            .navigationTitle("Conflict").navigationBarTitleDisplayMode(.inline)
        }
    }
}
