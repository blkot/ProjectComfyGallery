import CoreGraphics
import Foundation
import ImageIO

enum SpatialInputNormalizerError: LocalizedError, Sendable {
    case decodeFailed
    case encodeFailed

    var errorDescription: String? {
        switch self {
        case .decodeFailed:
            "The source image could not be prepared for spatial generation."
        case .encodeFailed:
            "The spatial-generation image could not be encoded."
        }
    }
}

enum SpatialInputNormalizer {
    static let maximumPixelDimension = 16_384

    static func normalizedJPEGData(
        contentsOf sourceURL: URL,
        pixelLimit: Int = maximumPixelDimension
    ) async throws -> Data {
        let boundedPixelLimit = max(1, min(pixelLimit, maximumPixelDimension))

        return try await Task.detached(priority: .userInitiated) {
            guard
                let source = CGImageSourceCreateWithURL(sourceURL as CFURL, nil),
                let decodedImage = CGImageSourceCreateThumbnailAtIndex(
                    source,
                    0,
                    [
                        kCGImageSourceCreateThumbnailFromImageAlways: true,
                        kCGImageSourceCreateThumbnailWithTransform: true,
                        kCGImageSourceShouldCacheImmediately: true,
                        kCGImageSourceThumbnailMaxPixelSize: boundedPixelLimit
                    ] as CFDictionary
                )
            else {
                throw SpatialInputNormalizerError.decodeFailed
            }

            guard
                let colorSpace = CGColorSpace(name: CGColorSpace.sRGB),
                let context = CGContext(
                    data: nil,
                    width: decodedImage.width,
                    height: decodedImage.height,
                    bitsPerComponent: 8,
                    bytesPerRow: 0,
                    space: colorSpace,
                    bitmapInfo: CGBitmapInfo.byteOrder32Big.rawValue
                        | CGImageAlphaInfo.noneSkipLast.rawValue
                )
            else {
                throw SpatialInputNormalizerError.decodeFailed
            }

            let bounds = CGRect(
                x: 0,
                y: 0,
                width: decodedImage.width,
                height: decodedImage.height
            )
            context.setFillColor(gray: 0, alpha: 1)
            context.fill(bounds)
            context.interpolationQuality = .high
            context.draw(decodedImage, in: bounds)

            guard let normalizedImage = context.makeImage() else {
                throw SpatialInputNormalizerError.decodeFailed
            }

            let output = NSMutableData()
            guard
                let destination = CGImageDestinationCreateWithData(
                    output,
                    "public.jpeg" as CFString,
                    1,
                    nil
                )
            else {
                throw SpatialInputNormalizerError.encodeFailed
            }
            CGImageDestinationAddImage(
                destination,
                normalizedImage,
                [
                    kCGImageDestinationLossyCompressionQuality: 0.96
                ] as CFDictionary
            )
            guard CGImageDestinationFinalize(destination) else {
                throw SpatialInputNormalizerError.encodeFailed
            }
            return output as Data
        }.value
    }
}
