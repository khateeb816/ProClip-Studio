import Foundation

enum AudioMode: String, CaseIterable, Identifiable {
    case background = "Background Only"
    case mix = "Mix (Original + Bg)"
    case original = "Original Only"
    
    var id: String { self.rawValue }
}

enum AspectRatio: String, CaseIterable, Identifiable {
    case original = "Original (No Crop)"
    case nineSixteen = "9:16 (TikTok/Reels)"
    case sixteenNine = "16:9 (YouTube)"
    case oneOne = "1:1 (Square)"
    case fourFive = "4:5 (Portrait)"
    
    var id: String { self.rawValue }
    
    // Helper to get ratio float
    var ratio: CGFloat? {
        switch self {
        case .original: return nil
        case .nineSixteen: return 9.0/16.0
        case .sixteenNine: return 16.0/9.0
        case .oneOne: return 1.0
        case .fourFive: return 4.0/5.0
        }
    }
}

enum Resolution: String, CaseIterable, Identifiable {
    case original = "Original"
    case k4 = "4K"
    case p1080 = "1080p"
    case p720 = "720p"
    case p480 = "480p"
    
    var id: String { self.rawValue }
    
    // Helper for approximate width (height depends on AR)
    // Or simpler: target height (standard)
    var targetHeight: CGFloat? {
        switch self {
        case .original: return nil
        case .k4: return 2160
        case .p1080: return 1080
        case .p720: return 720
        case .p480: return 480
        }
    }
}

enum FPS: String, CaseIterable, Identifiable {
    case source = "Source"
    case fps60 = "60"
    case fps30 = "30"
    case fps24 = "24"
    
    var id: String { self.rawValue }
}

enum ClipCountMode: String, CaseIterable, Identifiable {
    case automatic = "Automatic"
    case custom = "Custom"
    
    var id: String { self.rawValue }
}

struct ClipJobSettings {
    var videoURL: URL
    var audioURL: URL?
    var duration: Double
    var audioMode: AudioMode
    var aspectRatio: AspectRatio
    var resolution: Resolution
    var fps: FPS
    var countMode: ClipCountMode
    var customCount: Int
    
    // For free crop not implemented in V1 per request, but good to have placeholders
    var customCropRect: CGRect?
}

struct ExportLog: Identifiable {
    let id = UUID()
    let timestamp: Date = Date()
    let message: String
    let type: LogType
    
    enum LogType {
        case info
        case success
        case error
    }
}
