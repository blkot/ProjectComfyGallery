import Foundation

enum SampleData {
    static let sampleReviewItemJSON = """
    {
      "session": {"id": "sample-session", "current_cursor": 0, "candidate_count": 10},
      "position": 0,
      "media": {"id": "sample-media", "kind": "image", "preview_url": "/preview", "playback_url": null, "width": 1024, "height": 1536, "duration_seconds": null},
      "prompts": [{"role": "positive", "label": "Prompt", "text": "A serene mountain landscape at golden hour with soft clouds."}],
      "evaluations": [
        {
          "id": "sample-eval",
          "evaluation_kind": "base",
          "progress_state": "not_started",
          "is_trash": false,
          "version": 1,
          "criteria": [
            {"id": "c1", "label": "Aesthetic appeal", "description": "Overall visual quality", "min_value": 0, "max_value": 10},
            {"id": "c2", "label": "Prompt adherence", "description": "How well the image follows the prompt", "min_value": 0, "max_value": 10}
          ],
          "scores": []
        }
      ]
    }
    """.data(using: .utf8)!
}
