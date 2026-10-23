// Face boxes for every image in a folder, via Apple Vision (no OpenCV needed).
// swiftc -O faces.swift -o ~/.cache/vstudio/faces ; faces <dir> > faces.json
// Output: {"frame_0001.jpg": [[x, y, w, h, confidence], ...]} — normalised 0..1, origin TOP-left.
import Foundation
import Vision
import AppKit

let dir = CommandLine.arguments[1]
let files = try FileManager.default.contentsOfDirectory(atPath: dir).filter { $0.hasSuffix(".jpg") }.sorted()
var out: [String: [[Double]]] = [:]
for f in files {
    guard let img = NSImage(contentsOfFile: dir + "/" + f),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNDetectFaceRectanglesRequest()
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    out[f] = (req.results ?? []).map { r in
        let b = r.boundingBox
        return [Double(b.minX), Double(1 - b.maxY), Double(b.width), Double(b.height), Double(r.confidence)]
    }
}
let data = try JSONSerialization.data(withJSONObject: out, options: [.sortedKeys])
FileHandle.standardOutput.write(data)
