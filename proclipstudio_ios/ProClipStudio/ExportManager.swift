import Foundation
import AVFoundation

class ExportManager: NSObject {
    static let shared = ExportManager()
    
    func export(composition: AVComposition,
                videoComposition: AVVideoComposition?,
                audioMix: AVAudioMix?,
                outputURL: URL,
                quality: String = AVAssetExportPresetHighestQuality,
                completion: @escaping (Result<URL, Error>) -> Void) {
        
        guard let session = AVAssetExportSession(asset: composition, presetName: quality) else {
            completion(.failure(NSError(domain: "ExportManager", code: -1, userInfo: [NSLocalizedDescriptionKey: "Could not create ExportSession"])))
            return
        }
        
        session.outputURL = outputURL
        session.outputFileType = .mp4
        session.videoComposition = videoComposition
        session.audioMix = audioMix
        session.shouldOptimizeForNetworkUse = true
        
        session.exportAsynchronously {
            DispatchQueue.main.async {
                switch session.status {
                case .completed:
                    completion(.success(outputURL))
                case .failed:
                    completion(.failure(session.error ?? NSError(domain: "ExportManager", code: -2, userInfo: [NSLocalizedDescriptionKey: "Unknown Error"])))
                case .cancelled:
                    completion(.failure(NSError(domain: "ExportManager", code: -3, userInfo: [NSLocalizedDescriptionKey: "Cancelled"])))
                default:
                    break
                }
            }
        }
    }
}
