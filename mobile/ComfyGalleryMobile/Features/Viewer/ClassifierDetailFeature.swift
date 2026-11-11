import Foundation
import Observation

@MainActor
@Observable
final class ClassifierDetailFeature {
    private(set) var result: ClassifierStatusResponse?
    private(set) var isLoading = false
    private(set) var isWorking = false
    private(set) var errorMessage: String?
    private(set) var feedback: String?

    private let mediaID: String
    private let service: any ClassifierServicing

    init(mediaID: String, service: any ClassifierServicing) {
        self.mediaID = mediaID
        self.service = service
    }

    var assessment: ClassifierAssessment? { result?.assessment }
    var review: ClassifierReview? { result?.review }
    var isProcessing: Bool {
        ["queued", "running"].contains(result?.assessment?.status ?? result?.job?.status ?? "")
    }

    var assessmentSummary: MediaSafetyAssessmentSummary? {
        guard let assessment else { return nil }
        return MediaSafetyAssessmentSummary(
            status: assessment.status,
            label: assessment.label,
            suggestedRating: assessment.suggestedRating,
            confidence: assessment.confidence,
            needsReview: assessment.needsReview
        )
    }

    var reviewSummary: MediaSafetyReviewSummary? {
        guard let review else { return nil }
        return MediaSafetyReviewSummary(rating: review.rating, reviewedAt: review.reviewedAt)
    }

    func load() async {
        guard !isLoading else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            result = try await service.status(mediaID: mediaID)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func pollWhileVisible() async {
        while !Task.isCancelled, isProcessing {
            do { try await Task.sleep(for: .seconds(2)) }
            catch { return }
            await load()
        }
    }

    func classifyAgain() async {
        guard !isWorking, !isProcessing else { return }
        isWorking = true
        errorMessage = nil
        feedback = nil
        defer { isWorking = false }
        do {
            let batch = try await service.classify(mediaIDs: [mediaID], force: assessment?.status == "completed")
            feedback = "已排队 \(batch.queuedCount) 项 · 复用 \(batch.reusedCount) 项 · 跳过 \(batch.skippedCount) 项"
            if batch.queueFailedCount > 0 {
                errorMessage = "有 \(batch.queueFailedCount) 项无法加入分析队列。"
            }
            await load()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func setHumanRating(_ rating: ClassifierRating) async {
        guard rating.isHumanRating, !isWorking else { return }
        isWorking = true
        errorMessage = nil
        feedback = nil
        defer { isWorking = false }
        do {
            _ = try await service.setHumanRating(mediaID: mediaID, rating: rating)
            feedback = "人工分级已保存。"
            await load()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func clearHumanRating() async {
        guard review != nil, !isWorking else { return }
        isWorking = true
        errorMessage = nil
        feedback = nil
        defer { isWorking = false }
        do {
            try await service.clearHumanRating(mediaID: mediaID)
            feedback = "已清除人工分级，恢复 AI 建议。"
            await load()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
