import CoreGraphics
import Foundation
import ImageIO
import XCTest
@testable import ComfyGalleryXR

final class SpatialInputNormalizerTests: XCTestCase {
    func testProducesBoundedJPEGWithVisibleColor() async throws {
        let sourceData = try makeWideGamutSource()
        let sourceURL = FileManager.default.temporaryDirectory
            .appending(path: "\(UUID().uuidString).png")
        try sourceData.write(to: sourceURL)
        defer { try? FileManager.default.removeItem(at: sourceURL) }

        let testPixelLimit = 4_096
        let normalized = try await SpatialInputNormalizer.normalizedJPEGData(
            contentsOf: sourceURL,
            pixelLimit: testPixelLimit
        )
        let source = try XCTUnwrap(
            CGImageSourceCreateWithData(normalized as CFData, nil)
        )
        XCTAssertEqual(CGImageSourceGetType(source) as String?, "public.jpeg")

        let image = try XCTUnwrap(CGImageSourceCreateImageAtIndex(source, 0, nil))
        XCTAssertEqual(SpatialInputNormalizer.maximumPixelDimension, 16_384)
        XCTAssertEqual(image.width, testPixelLimit)
        XCTAssertLessThan(image.height, image.width)
        XCTAssertGreaterThan(try averageLuminance(of: image), 0.25)
    }

    func testPreservesCommonGalleryImageDimensions() async throws {
        let sourceData = try makeWideGamutSource(width: 1_024, height: 1_536)
        let sourceURL = FileManager.default.temporaryDirectory
            .appending(path: "\(UUID().uuidString).png")
        try sourceData.write(to: sourceURL)
        defer { try? FileManager.default.removeItem(at: sourceURL) }

        let normalized = try await SpatialInputNormalizer.normalizedJPEGData(
            contentsOf: sourceURL
        )
        let source = try XCTUnwrap(
            CGImageSourceCreateWithData(normalized as CFData, nil)
        )
        let image = try XCTUnwrap(CGImageSourceCreateImageAtIndex(source, 0, nil))

        XCTAssertEqual(image.width, 1_024)
        XCTAssertEqual(image.height, 1_536)
    }

    private func makeWideGamutSource(
        width: Int = 5_000,
        height: Int = 1_000
    ) throws -> Data {
        let colorSpace = try XCTUnwrap(CGColorSpace(name: CGColorSpace.displayP3))
        let context = try XCTUnwrap(
            CGContext(
                data: nil,
                width: width,
                height: height,
                bitsPerComponent: 8,
                bytesPerRow: 0,
                space: colorSpace,
                bitmapInfo: CGBitmapInfo.byteOrder32Big.rawValue
                    | CGImageAlphaInfo.premultipliedLast.rawValue
            )
        )
        context.setFillColor(red: 0.9, green: 0.35, blue: 0.1, alpha: 1)
        context.fill(CGRect(x: 0, y: 0, width: width, height: height))
        let image = try XCTUnwrap(context.makeImage())

        let output = NSMutableData()
        let destination = try XCTUnwrap(
            CGImageDestinationCreateWithData(
                output,
                "public.png" as CFString,
                1,
                nil
            )
        )
        CGImageDestinationAddImage(destination, image, nil)
        XCTAssertTrue(CGImageDestinationFinalize(destination))
        return output as Data
    }

    private func averageLuminance(of image: CGImage) throws -> Double {
        let width = image.width
        let height = image.height
        var pixels = [UInt8](repeating: 0, count: width * height * 4)
        let colorSpace = try XCTUnwrap(CGColorSpace(name: CGColorSpace.sRGB))
        try pixels.withUnsafeMutableBytes { bytes in
            let context = try XCTUnwrap(
                CGContext(
                    data: bytes.baseAddress,
                    width: width,
                    height: height,
                    bitsPerComponent: 8,
                    bytesPerRow: width * 4,
                    space: colorSpace,
                    bitmapInfo: CGBitmapInfo.byteOrder32Big.rawValue
                        | CGImageAlphaInfo.premultipliedLast.rawValue
                )
            )
            context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
        }

        var total = 0.0
        var sampleCount = 0
        let sampleStride = max(1, (width * height) / 20_000)
        for pixelIndex in stride(from: 0, to: width * height, by: sampleStride) {
            let offset = pixelIndex * 4
            let red = Double(pixels[offset]) / 255
            let green = Double(pixels[offset + 1]) / 255
            let blue = Double(pixels[offset + 2]) / 255
            total += 0.2126 * red + 0.7152 * green + 0.0722 * blue
            sampleCount += 1
        }
        return total / Double(sampleCount)
    }
}
