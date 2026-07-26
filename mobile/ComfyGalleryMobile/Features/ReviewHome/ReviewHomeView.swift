import SwiftUI

struct ReviewHomeView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var feature: ReviewHomeFeature
    @State private var showingNewSession = false
    @State private var selectedSession: ReviewSession?

    init(apiClient: APIClient) {
        _feature = State(initialValue: ReviewHomeFeature(apiClient: apiClient))
    }

    var body: some View {
        NavigationStack {
            List {
                if feature.isLoading && feature.summary == nil && feature.sessions.isEmpty {
                    Section {
                        HStack {
                            Spacer()
                            ProgressView()
                            Spacer()
                        }
                        .listRowBackground(Color.clear)
                    }
                }

                if let error = feature.errorMessage {
                    Section {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(error)
                                .foregroundStyle(.red)
                                .font(.caption)
                            Button("Retry") {
                                Task { await feature.load() }
                            }
                            .font(.caption)
                        }
                    }
                }

                if let summary = feature.summary {
                    Section("Overview") {
                        HStack {
                            Label("Not Started", systemImage: "circle")
                            Spacer()
                            Text("\(summary.notStartedCount)").foregroundStyle(.secondary)
                        }
                        HStack {
                            Label("In Progress", systemImage: "circle.dotted")
                            Spacer()
                            Text("\(summary.inProgressCount)").foregroundStyle(.secondary)
                        }
                        HStack {
                            Label("Complete", systemImage: "checkmark.circle.fill")
                            Spacer()
                            Text("\(summary.completeCount)").foregroundStyle(.secondary)
                        }
                    }

                    Section("Quick Actions") {
                        Button {
                            feature.configureForQuickAction(.inProgress)
                            showingNewSession = true
                        } label: {
                            Label("Resume In Progress (\(summary.inProgressCount))", systemImage: "arrow.counterclockwise")
                        }

                        Button {
                            feature.configureForQuickAction(.random)
                            showingNewSession = true
                        } label: {
                            Label("Start Random Review", systemImage: "shuffle")
                        }
                    }
                }

                let active = feature.sessions.filter { $0.status == .active }
                if !active.isEmpty {
                    Section("Active Sessions") {
                        ForEach(active) { sessionRow($0) }
                    }
                }

                let other = feature.sessions.filter { $0.status != .active }
                if !other.isEmpty {
                    Section("Recent Sessions") {
                        ForEach(other) { sessionRow($0) }
                    }
                }
            }
            .navigationTitle("Review")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button { showingNewSession = true } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showingNewSession) {
                NewSessionSheet(feature: feature) { session in
                    selectedSession = session
                }
            }
            .fullScreenCover(item: $selectedSession) { session in
                ReviewWorkspaceView(
                    feature: ReviewWorkspaceFeature(
                        sessionID: session.id,
                        apiClient: environment.apiClient,
                        mediaRepository: environment.mediaRepository,
                        commandQueue: environment.reviewCommandQueue,
                        localStore: environment.localStore
                    )
                )
            }
            .refreshable {
                await feature.load()
            }
            .task {
                await feature.load()
            }
        }
    }

    private func sessionRow(_ session: ReviewSession) -> some View {
        Button {
            selectedSession = session
        } label: {
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(session.name ?? session.sourceKind.rawValue.capitalized).font(.headline)
                    Spacer()
                    statusBadge(session.status)
                }
                if let cursor = session.currentCursor {
                    Text("Position: \(cursor) / \(session.candidateCount)")
                        .font(.caption).foregroundStyle(.secondary)
                }
                if let counts = session.progressCounts {
                    Text("\(counts.complete) complete · \(counts.inProgress) in progress")
                        .font(.caption2).foregroundStyle(.secondary)
                }
            }
        }
        .swipeActions {
            Button("Delete", role: .destructive) {
                Task { await feature.deleteSession(session) }
            }
        }
    }

    @ViewBuilder
    private func statusBadge(_ status: SessionStatus) -> some View {
        switch status {
        case .active:
            Text("Active").font(.caption)
                .padding(.horizontal, 8).padding(.vertical, 2)
                .background(.green.opacity(0.15))
                .foregroundStyle(.green)
                .clipShape(Capsule())
        case .finished:
            Text("Finished").font(.caption).foregroundStyle(.secondary)
                .padding(.horizontal, 8).padding(.vertical, 2)
        case .abandoned:
            Text("Abandoned").font(.caption).foregroundStyle(.secondary)
                .padding(.horizontal, 8).padding(.vertical, 2)
        }
    }
}
