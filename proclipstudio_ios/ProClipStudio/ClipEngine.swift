import Foundation
import AVFoundation
import UIKit

class ClipEngine: ObservableObject {
    @Published var isProcessing = false
    @Published var progress: Double = 0.0
    @Published var logs: [ExportLog] = []
    
    // Cancellation
    private var isCancelled = false
    
    func log(_ msg: String, type: ExportLog.LogType = .info) {
        DispatchQueue.main.async {
            self.logs.append(ExportLog(message: msg, type: type))
            print("[ClipEngine] \(msg)")
        }
    }
    
    func cancel() {
        self.isCancelled = true
        log("Cancelling operation...", type: .error)
    }
    
    func processAndExport(settings: ClipJobSettings) async {
        DispatchQueue.main.async {
            self.isProcessing = true
            self.progress = 0.0
            self.logs.removeAll()
            self.isCancelled = false
        }
        
        log("Starting Batch Processing...")
        
        let videoAsset = AVAsset(url: settings.videoURL)
        
        do {
            let videoDur = try await videoAsset.load(.duration).seconds
            if videoDur == 0 { throw NSError(domain: "ClipEngine", code: 1, userInfo: [NSLocalizedDescriptionKey: "Video duration is 0"]) }
            
            // 1. Calculate Clip Counts
            let targetDur = settings.duration
            
            // Logic from python: if video < dur, loop it.
            // Effective duration for counting clips?
            // If we loop, effective source is infinite? No, we produce clips of 'targetDur'.
            
            // "If automatic, we usually take max_clips_possible" (based on original video length)
            // But if video is shorter, we assume at least 1 clip (looped).
            
            var totalClips = 0
            if settings.countMode == .custom {
                totalClips = settings.customCount
            } else {
                totalClips = Int(floor(videoDur / targetDur))
            }
            if totalClips < 1 { totalClips = 1 }
            
            log("Plan: \(totalClips) clip(s) of \(targetDur)s each.")
            
            // Prepare Loop Audio Asset if needed
            var bgAsset: AVAsset?
            if let audioURL = settings.audioURL, settings.audioMode != .original {
                bgAsset = AVAsset(url: audioURL)
            }
            
            // Create Output Directory
            let fileManager = FileManager.default
            let documentsURL = fileManager.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let outputFolder = documentsURL.appendingPathComponent("ProClip_Exports_\(Int(Date().timeIntervalSince1970))")
            try fileManager.createDirectory(at: outputFolder, withIntermediateDirectories: true)
            
            log("Saving to: \(outputFolder.lastPathComponent)")
            
            for i in 0..<totalClips {
                if isCancelled { break }
                
                let clipNum = i + 1
                log("Processing Clip \(clipNum)/\(totalClips)...")
                
                // Calculate Time Range
                // Logic:
                // Clip 1: 0 to 10
                // Clip 2: 10 to 20
                // If start > videoDur, we need to loop?
                // The Python logic says:
                // "If video < dur, loop it." -> This means the *source* is effectively looped.
                // But generally, we iterate i * dur.
                
                // We construct a specific Composition for THIS clip.
                // We want to fill 'targetDur' seconds.
                
                let composition = AVMutableComposition()
                guard let compVideoTrack = composition.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid) else { continue }
                
                let videoTrack = try await videoAsset.loadTracks(withMediaType: .video).first!
                
                // Video Logic: Fill 'targetDur' by looping videoAsset starting from global offset
                // Global Offset = i * targetDur.
                // We emulate a "Simulated Infinite Tape" of the video repeated.
                
                var currentWritePos = CMTime.zero
                var filledDuration = 0.0
                let globalStartOffset = Double(i) * targetDur
                
                // Where are we in the "Infinite Tape"?
                // We need to extract [globalStartOffset, globalStartOffset + targetDur]
                
                // Map this to the real video asset (length V).
                // segment start in real video = globalStartOffset % V
                // This segment might run to end of V, then wrap around to 0.
                
                while filledDuration < targetDur {
                    let needed = targetDur - filledDuration
                    
                    let realVideoStart = (globalStartOffset + filledDuration).truncatingRemainder(dividingBy: videoDur)
                    
                    // How much can we take from real video before it ends?
                    let remainingInReal = videoDur - realVideoStart
                    
                    let chunkDur = min(needed, remainingInReal)
                    
                    let segmentTimeRange = CMTimeRange(start: CMTime(seconds: realVideoStart, preferredTimescale: 600),
                                                       duration: CMTime(seconds: chunkDur, preferredTimescale: 600))
                    
                    try compVideoTrack.insertTimeRange(segmentTimeRange, of: videoTrack, at: currentWritePos)
                    
                    // Update Pointers
                    currentWritePos = CMTimeAdd(currentWritePos, segmentTimeRange.duration)
                    filledDuration += chunkDur
                }
                
                // Audio Logic
                // 1. Original Audio (if Mix or Original)
                if settings.audioMode == .mix || settings.audioMode == .original {
                    if let audioTrack = try await videoAsset.loadTracks(withMediaType: .audio).first {
                        let compAudioTrack = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid)
                        
                        // Same Loop Logic for Original Audio
                        currentWritePos = CMTime.zero
                        filledDuration = 0.0
                        
                        while filledDuration < targetDur {
                            let needed = targetDur - filledDuration
                            let realStart = (globalStartOffset + filledDuration).truncatingRemainder(dividingBy: videoDur)
                            let remainingInReal = videoDur - realStart
                            let chunkDur = min(needed, remainingInReal)
                            
                            let segmentTimeRange = CMTimeRange(start: CMTime(seconds: realStart, preferredTimescale: 600),
                                                               duration: CMTime(seconds: chunkDur, preferredTimescale: 600))
                            
                            try compAudioTrack?.insertTimeRange(segmentTimeRange, of: audioTrack, at: currentWritePos)
                             
                            currentWritePos = CMTimeAdd(currentWritePos, segmentTimeRange.duration)
                            filledDuration += chunkDur
                        }
                    }
                }
                
                // 2. Background Audio (if Mix or Background)
                if let bgAsset = bgAsset, (settings.audioMode == .mix || settings.audioMode == .background) {
                   if let bgTrack = try await bgAsset.loadTracks(withMediaType: .audio).first {
                       let bgCompTrack = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid)
                       let bgDur = try await bgAsset.load(.duration).seconds
                       
                       // For BG, we always start from 0 for every clip? Or continuous?
                       // App.py:
                       // "if bg_audio.duration < dur: loop it"
                       // It creates a subclip(0, dur).
                       // So it ALWAYS starts from 0 for EACH clip.
                       
                       currentWritePos = CMTime.zero
                       filledDuration = 0.0
                       
                       while filledDuration < targetDur {
                           let needed = targetDur - filledDuration
                           let startInBg = 0.0 + filledDuration // Actually if we want to loop from 0:
                           // No, python code: `concatenate_audioclips([bg_audio]*n).subclipped(0, dur)`
                           // This implies we start from 0 at the beginning of the clip result.
                           // But do we restart the song for each clip? Yes.
                           
                           let loopReadPos = filledDuration.truncatingRemainder(dividingBy: bgDur)
                           let remainingInBg = bgDur - loopReadPos
                           let chunkDur = min(needed, remainingInBg)
                           
                           let segmentTimeRange = CMTimeRange(start: CMTime(seconds: loopReadPos, preferredTimescale: 600),
                                                              duration: CMTime(seconds: chunkDur, preferredTimescale: 600))
                           
                           try bgCompTrack?.insertTimeRange(segmentTimeRange, of: bgTrack, at: currentWritePos)
                           
                           currentWritePos = CMTimeAdd(currentWritePos, segmentTimeRange.duration)
                           filledDuration += chunkDur
                       }
                   }
                }
                
                // Composition Done. Now VideoComposition for Layer instructions (Crop/Resize).
                
                // Calculate Output Resolution
                var renderSize = try await videoTrack.load(.naturalSize) // Default
                // If transformed?
                let t = try await videoTrack.load(.preferredTransform)
                if (t.b == 1.0 && t.c == -1.0) || (t.a == 0 && t.d == 0) {
                     // Portrait/Rotated 90
                     renderSize = CGSize(width: renderSize.height, height: renderSize.width)
                }
                
                // Apply User Resolution Settings
                if let targetH = settings.resolution.targetHeight {
                    // Python logic:
                    // If Landscape (w > h): h = targetH.
                    // If Portrait (h > w): w = targetH. (Actually python said "resized(width=target_res_val)" for portrait)
                    
                    let ar = renderSize.width / renderSize.height
                    if renderSize.width >= renderSize.height {
                        // Landscape
                        let newH = targetH
                        let newW = newH * ar
                        renderSize = CGSize(width: newW, height: newH)
                    } else {
                        // Portrait
                        let newW = targetH // e.g. 1080p width
                        let newH = newW / ar
                        renderSize = CGSize(width: newW, height: newH)
                    }
                }
               
                // Force Even Dimensions
                var finalW = Int(renderSize.width)
                var finalH = Int(renderSize.height)
                if finalW % 2 != 0 { finalW -= 1 }
                if finalH % 2 != 0 { finalH -= 1 }
                renderSize = CGSize(width: finalW, height: finalH)
                
                // Crop/Aspect Ratio
                // For V1, user said "UI doesn't need crop/preview canvas", but logic must "Replicate all main features".
                // I will implement Center Crop for the chosen AR.
                
                var cropRect = CGRect(origin: .zero, size: renderSize)
                
                if let targetRatio = settings.aspectRatio.ratio {
                    // Target AR
                    let currentAr = renderSize.width / renderSize.height
                   
                    if currentAr > targetRatio {
                        // Too wide: Crop Width
                        let newW = renderSize.height * targetRatio
                        let xOff = (renderSize.width - newW) / 2
                        cropRect = CGRect(x: xOff, y: 0, width: newW, height: renderSize.height)
                    } else {
                         // Too tall: Crop Height
                         let newH = renderSize.width / targetRatio
                         let yOff = (renderSize.height - newH) / 2
                         cropRect = CGRect(x: 0, y: yOff, width: renderSize.width, height: newH)
                    }
                    
                    // Update render size to the crop size
                    finalW = Int(cropRect.width)
                    finalH = Int(cropRect.height)
                    if finalW % 2 != 0 { finalW -= 1 }
                    if finalH % 2 != 0 { finalH -= 1 }
                    // Update crop rect if we shaved a pixel
                    cropRect.size = CGSize(width: finalW, height: finalH)
                    // Does this mean renderSize becomes this?
                    // Yes, the output video should be this size.
                    renderSize = cropRect.size
                }
                
                // Build Video Composition
                let videoComposition = AVMutableVideoComposition()
                videoComposition.renderSize = renderSize
                videoComposition.frameDuration = CMTime(value: 1, timescale: 30) // Default 30 FPS
                if settings.fps != .source, let val = Double(settings.fps.rawValue) {
                     videoComposition.frameDuration = CMTime(value: 1, timescale: Int32(val))
                }
                 
                let instruction = AVMutableVideoCompositionInstruction()
                instruction.timeRange = CMTimeRange(start: .zero, duration: composition.duration)
                
                let layerInstruction = AVMutableVideoCompositionLayerInstruction(assetTrack: compVideoTrack)
                
                // Transform Logic
                // 1. Move negative origin of crop
                // 2. Scale to render size (if res changed)
                
                // Actually, renderSize is the FINAL output size.
                // We have source video (Track scale).
                // We need to transform it such that 'cropRect' fills 'renderSize'.
                
                // Step A: Calculate Scale to match 'Resolution' target loop above.
                // We calculated 'renderSize' before cropping based on resolution.
                // But now 'renderSize' is the Cropped size.
                
                // Let's re-evaluate standard flow:
                // 1. Source Frame
                // 2. Scale (to meet resolution target)
                // 3. Center Crop (to meet AR target)
                
                // We need to construct the Transform.
                let naturalSize = try await videoTrack.load(.naturalSize)
                
                // Fix orientation in transform
                var baseTransform = try await videoTrack.load(.preferredTransform)
                // If portrait, width/height are swapped in naturalSize vs internal? 
                // AVFoundation handles preferredTransform automatically in layer instructions usually? 
                // No, we often need to manually apply it if we are messing with coordinates.
                
                // To keep it simple: 
                // Let's assume standard orientation for math, apply valid transform.
                
                // Simplified Math:
                // We want KeyRect (CropRect in Source Coordinates) to map to OutputRect (0,0,W,H).
                
                // First, determine Source Scale factor.
                // Based on "Resolution" logic:
                // If Landscape, newH = targetH. Scale = targetH / sourceH.
                
                var scaleFactor = 1.0
                if let targetH = settings.resolution.targetHeight {
                     // Assume orientation logic handled.
                     let srcH = (t.b == 1.0 && t.c == -1.0) || (t.a == 0 && t.d == 0) ? naturalSize.width : naturalSize.height
                     scaleFactor = targetH / srcH
                }
                
                // Apply Scale
                let scaledT = baseTransform.concatenating(CGAffineTransform(scaleX: scaleFactor, y: scaleFactor))
                
                // Apply Crop Translation
                // We need to shift so that the CropRect's origin is at (0,0).
                // CropRect was calculated based on "scaled" dimensions in logic above.
                // cropRect.origin.x is the offset in the scaled space.
                
                let translateT = scaledT.concatenating(CGAffineTransform(translationX: -cropRect.origin.x, y: -cropRect.origin.y))
                
                layerInstruction.setTransform(translateT, at: .zero)
                instruction.layerInstructions = [layerInstruction]
                videoComposition.instructions = [instruction]
                
                
                // Export
                let randomID = String(Int.random(in: 1000...9999))
                let dateFormatter = DateFormatter()
                dateFormatter.dateFormat = "ddMMyyyyHHmmss"
                let dateStr = dateFormatter.string(from: Date())
                let fileName = "\(dateStr)-PREMIUM-\(randomID)-CLIP-\(clipNum).mp4"
                
                let outURL = outputFolder.appendingPathComponent(fileName)
                
                // Await Export
                try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
                    ExportManager.shared.export(composition: composition,
                                                videoComposition: videoComposition,
                                                audioMix: nil,
                                                outputURL: outURL) { result in
                        switch result {
                        case .success(_):
                            continuation.resume()
                        case .failure(let error):
                             continuation.resume(throwing: error)
                        }
                    }
                }
                
                log("Completed: \(fileName)", type: .success)
                
                // Update Progress
                 DispatchQueue.main.async {
                    self.progress = Double(clipNum) / Double(totalClips)
                 }
            }
            
            log("All operations completed!", type: .success)
            
        } catch {
            log("Critical Error: \(error.localizedDescription)", type: .error)
        }
        
        DispatchQueue.main.async {
            self.isProcessing = false
        }
    }
}
