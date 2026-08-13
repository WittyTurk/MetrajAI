import AppKit
import Foundation
import PDFKit
import Vision

struct OCRPage: Codable {
    let page: Int
    let text: String
    let confidence: Float
}

guard CommandLine.arguments.count == 2 else {
    fputs("usage: metrajai-ocr <document.pdf>\n", stderr)
    exit(2)
}

let inputURL = URL(fileURLWithPath: CommandLine.arguments[1])
guard let document = PDFDocument(url: inputURL) else {
    fputs("PDF could not be opened\n", stderr)
    exit(3)
}

var result: [OCRPage] = []
for pageIndex in 0..<document.pageCount {
    guard let page = document.page(at: pageIndex) else { continue }
    let bounds = page.bounds(for: .mediaBox)
    let longest = max(bounds.width, bounds.height)
    let renderScale = longest > 0 ? min(3.0, 2400.0 / longest) : 2.0
    let image = page.thumbnail(
        of: NSSize(width: bounds.width * renderScale, height: bounds.height * renderScale),
        for: .mediaBox
    )
    var proposedRect = NSRect(origin: .zero, size: image.size)
    guard let cgImage = image.cgImage(
        forProposedRect: &proposedRect,
        context: nil,
        hints: nil
    ) else { continue }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    let supported = try? request.supportedRecognitionLanguages()
    if supported?.contains("tr-TR") == true {
        request.recognitionLanguages = ["tr-TR", "en-US"]
    }
    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    do {
        try handler.perform([request])
    } catch {
        continue
    }
    let observations = request.results ?? []
    let candidates = observations.compactMap { $0.topCandidates(1).first }
    let text = candidates.map(\.string).joined(separator: "\n")
    let confidence = candidates.isEmpty
        ? 0
        : candidates.map(\.confidence).reduce(0, +) / Float(candidates.count)
    result.append(OCRPage(page: pageIndex + 1, text: text, confidence: confidence))
}

let encoder = JSONEncoder()
encoder.outputFormatting = [.withoutEscapingSlashes]
let data = try encoder.encode(result)
FileHandle.standardOutput.write(data)
FileHandle.standardOutput.write(Data("\n".utf8))
