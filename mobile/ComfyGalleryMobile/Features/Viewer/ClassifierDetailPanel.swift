import SwiftUI

struct ClassifierDetailPanel: View {
    let item: MobileMediaSummary
    let service: any ClassifierServicing
    let onProjection: (MediaSafetyAssessmentSummary?, MediaSafetyReviewSummary?) -> Void
    let setContentRating: (String) async throws -> Void

    @State private var feature: ClassifierDetailFeature
    @State private var confirmingClear = false
    @State private var contentRating: String?
    @State private var contentRatingError: String?
    @State private var isChangingContentRating = false

    init(
        item: MobileMediaSummary,
        service: any ClassifierServicing,
        onProjection: @escaping (MediaSafetyAssessmentSummary?, MediaSafetyReviewSummary?) -> Void,
        setContentRating: @escaping (String) async throws -> Void
    ) {
        self.item = item
        self.service = service
        self.onProjection = onProjection
        self.setContentRating = setContentRating
        _feature = State(initialValue: ClassifierDetailFeature(mediaID: item.id, service: service))
        _contentRating = State(initialValue: item.contentRating)
    }

    var body: some View {
        classifierSection
        humanReviewSection
        legacyRatingSection
            .task(id: item.id) {
                await feature.load()
                await refreshUntilComplete()
            }
            .confirmationDialog("清除人工分级？", isPresented: $confirmingClear, titleVisibility: .visible) {
                Button("清除人工分级", role: .destructive) {
                    Task {
                        await feature.clearHumanRating()
                        publishProjection()
                    }
                }
            } message: {
                Text("清除后将恢复 AI 建议；如果没有 AI 结果，媒体会重新显示为未分类。")
            }
    }

    private var classifierSection: some View {
        Section("内容分类") {
            if feature.isLoading && feature.result == nil {
                ProgressView("正在读取分类结果…")
            } else if let result = feature.result {
                effectiveResult(result)
                if feature.isProcessing {
                    Label(result.assessment?.status == "queued" ? "等待分类任务" : "正在分析照片", systemImage: "hourglass")
                        .foregroundStyle(.secondary)
                } else if let error = result.assessment?.errorMessage {
                    Label(error, systemImage: "exclamationmark.triangle.fill")
                        .foregroundStyle(.red)
                }

                Button {
                    Task { await feature.classifyAgain(); await refreshUntilComplete() }
                } label: {
                    Label(classifyButtonTitle, systemImage: "sparkles")
                        .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                }
                .disabled(feature.isWorking || feature.isProcessing)

                if let feedback = feature.feedback {
                    Label(feedback, systemImage: "checkmark.circle")
                        .font(.footnote).foregroundStyle(.secondary)
                }

                if let assessment = result.assessment, assessment.status == "completed" {
                    DisclosureGroup("分析依据") {
                        ForEach(Array(assessment.scores.sorted { $0.value > $1.value }), id: \.key) { label, score in
                            HStack {
                                Text(label.capitalized)
                                if label.caseInsensitiveCompare(assessment.label ?? "") == .orderedSame {
                                    Text("AI 建议").font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                                Text(score, format: .percent.precision(.fractionLength(1))).monospacedDigit()
                            }
                            .accessibilityElement(children: .combine)
                        }

                        if assessment.nudityDetectorStatus == "completed" {
                            LabeledContent("区域检测") {
                                Text(assessment.nudityDetections.isEmpty ? "未发现检测区域" : "\(assessment.nudityDetections.count) 项")
                            }
                            ForEach(assessment.nudityDetections) { detection in
                                LabeledContent(detection.detectionClass.replacingOccurrences(of: "_", with: " ").capitalized) {
                                    Text(detection.score, format: .percent.precision(.fractionLength(1)))
                                }
                            }
                        } else {
                            Text("额外区域检测未运行。")
                                .font(.footnote).foregroundStyle(.secondary)
                        }
                        LabeledContent("分析引擎", value: assessment.inferenceBackend.uppercased())
                    }
                }
            } else {
                ContentUnavailableView("尚无分类结果", systemImage: "sparkles", description: Text("你可以按需请求 AI 分类。"))
                Button {
                    Task { await feature.classifyAgain(); await refreshUntilComplete() }
                } label: {
                    Label("开始 AI 分类", systemImage: "sparkles")
                        .frame(maxWidth: .infinity, minHeight: 44, alignment: .center)
                }
                .disabled(feature.isWorking)
            }

            if let error = feature.errorMessage {
                Label(error, systemImage: "exclamationmark.triangle.fill")
                    .font(.footnote).foregroundStyle(.red)
            }
            if let error = feature.result == nil ? feature.errorMessage : nil {
                Button("重新读取状态") { Task { await feature.load() } }
                    .accessibilityHint(error)
            }
        }
    }

    @ViewBuilder private func effectiveResult(_ result: ClassifierStatusResponse) -> some View {
        if let review = result.review {
            LabeledContent("当前生效", value: "\(review.rating.title) · 人工确认")
            if let assessment = result.assessment, assessment.status == "completed", let suggestion = assessment.suggestedRating {
                Text(review.rating == suggestion ? "人工分级与 AI 建议一致。" : "人工分级覆盖了 AI 建议（\(suggestion.title)）。")
                    .font(.footnote).foregroundStyle(.secondary)
            }
        } else if let assessment = result.assessment, assessment.status == "completed", let rating = assessment.suggestedRating {
            LabeledContent("当前生效", value: "\(rating.title) · AI 建议")
            if let confidence = assessment.confidence {
                LabeledContent("模型置信度", value: confidence.formatted(.percent.precision(.fractionLength(1))))
            }
            if assessment.needsReview {
                Label("模型建议人工复核", systemImage: "questionmark.circle.fill")
                    .foregroundStyle(.orange)
            }
        } else if let assessment = result.assessment, assessment.status == "failed" {
            LabeledContent("当前状态", value: "分析失败")
        } else if feature.isProcessing {
            LabeledContent("当前状态", value: "处理中")
        } else {
            LabeledContent("当前状态", value: "未分类")
        }
    }

    private var humanReviewSection: some View {
        Section("人工复核") {
            Text("人工分级独立保存，不会修改手动 SFW / NSFW 标记。")
                .font(.footnote).foregroundStyle(.secondary)
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                ForEach(ClassifierRating.allCases.filter(\.isHumanRating), id: \.self) { rating in
                    Button {
                        Task {
                            await feature.setHumanRating(rating)
                            publishProjection()
                        }
                    } label: {
                        Label(rating.title, systemImage: rating.symbol)
                            .frame(maxWidth: .infinity, minHeight: 48)
                    }
                    .buttonStyle(.bordered)
                    .tint(feature.review?.rating == rating ? .accentColor : .secondary)
                    .accessibilityValue(feature.review?.rating == rating ? "人工已选择" : "")
                    .disabled(feature.isWorking || feature.isLoading)
                }
            }
            if let review = feature.review {
                LabeledContent("复核时间", value: review.reviewedAt)
                Button("清除人工分级", systemImage: "arrow.uturn.backward") { confirmingClear = true }
                    .disabled(feature.isWorking)
            }
        }
    }

    private var legacyRatingSection: some View {
        Section("手动 SFW / NSFW") {
            Text("这是旧版内容标记，与 AI 建议和人工 classifier 分级彼此独立。")
                .font(.footnote).foregroundStyle(.secondary)
            HStack {
                ratingButton("sfw", label: "SFW", symbol: "checkmark.shield")
                ratingButton("nsfw", label: "NSFW", symbol: "exclamationmark.shield")
            }
            if isChangingContentRating { ProgressView("正在保存…") }
            if let contentRatingError { Text(contentRatingError).font(.footnote).foregroundStyle(.red) }
        }
    }

    private func ratingButton(_ value: String, label: String, symbol: String) -> some View {
        Button {
            guard !isChangingContentRating, contentRating != value else { return }
            isChangingContentRating = true
            contentRatingError = nil
            Task {
                do {
                    try await setContentRating(value)
                    contentRating = value
                } catch {
                    contentRatingError = error.localizedDescription
                }
                isChangingContentRating = false
            }
        } label: {
            Label(label, systemImage: symbol)
                .frame(maxWidth: .infinity, minHeight: 48)
                .background(contentRating == value ? Color.accentColor.opacity(0.16) : .clear, in: RoundedRectangle(cornerRadius: 10))
        }
        .buttonStyle(.bordered)
        .accessibilityValue(contentRating == value ? "已选择" : "")
        .disabled(isChangingContentRating)
    }

    private var classifyButtonTitle: String {
        feature.assessment?.status == "completed" ? "重新分析" : feature.assessment?.status == "failed" ? "重试 AI 分类" : "开始 AI 分类"
    }

    private func publishProjection() {
        onProjection(feature.assessmentSummary, feature.reviewSummary)
    }

    private func refreshUntilComplete() async {
        publishProjection()
        await feature.pollWhileVisible()
        publishProjection()
    }
}
