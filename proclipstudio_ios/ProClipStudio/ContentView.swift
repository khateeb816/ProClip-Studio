import SwiftUI
import AVKit

struct ContentView: View {
    @StateObject private var engine = ClipEngine()
    
    // Inputs
    @State private var videoURL: URL?
    @State private var audioURL: URL?
    
    // Settings
    @State private var duration: String = "60"
    @State private var audioMode: AudioMode = .mix
    @State private var countMode: ClipCountMode = .automatic
    @State private var customCount: String = "5"
    @State private var resolution: Resolution = .original
    @State private var fps: FPS = .source
    @State private var aspectRatio: AspectRatio = .original
    
    // UI State
    @State private var showVideoPicker = false
    @State private var showAudioPicker = false
    
    var body: some View {
        NavigationView {
            ZStack {
                Color(red: 0.1, green: 0.1, blue: 0.1).ignoresSafeArea()
                
                VStack(spacing: 0) {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 20) {
                            
                            // Header
                            Text("ProClip Studio")
                                .font(.system(size: 28, weight: .bold))
                                .foregroundColor(.white)
                                .padding(.top, 20)
                            
                            // 1. Media Source
                            SectionHeader(title: "MEDIA SOURCE")
                            
                            FileSelector(icon: "video.fill", title: "Video Source", path: videoURL?.lastPathComponent) {
                                showVideoPicker = true
                            }
                            .sheet(isPresented: $showVideoPicker) {
                                VideoPicker(selectedURL: $videoURL)
                            }
                            
                            FileSelector(icon: "music.note", title: "Background Audio", path: audioURL?.lastPathComponent) {
                                showAudioPicker = true
                            }
                            .sheet(isPresented: $showAudioPicker) {
                                AudioPicker(selectedURL: $audioURL)
                            }
                            
                            // 2. Configuration
                            SectionHeader(title: "CONFIGURATION")
                            
                            // Duration
                            HStack {
                                Text("Clip Duration (s)")
                                    .foregroundColor(.gray)
                                Spacer()
                                TextField("60", text: $duration)
                                    .keyboardType(.numberPad)
                                    .padding(8)
                                    .background(Color(white: 0.15))
                                    .cornerRadius(6)
                                    .frame(width: 80)
                                    .foregroundColor(.white)
                            }
                            
                            // Audio Mode
                            PickerView(title: "Audio Mode", selection: $audioMode)
                            
                            // Aspect Ratio
                            PickerView(title: "Aspect Ratio", selection: $aspectRatio)
                            
                            // Clip Count
                            PickerView(title: "Clip Count Mode", selection: $countMode)
                            
                            if countMode == .custom {
                                HStack {
                                    Text("Number of Clips")
                                        .foregroundColor(.gray)
                                    Spacer()
                                    TextField("5", text: $customCount)
                                        .keyboardType(.numberPad)
                                        .padding(8)
                                        .background(Color(white: 0.15))
                                        .cornerRadius(6)
                                        .frame(width: 80)
                                        .foregroundColor(.white)
                                }
                            }
                            
                            // 3. Export Settings
                            SectionHeader(title: "EXPORT SETTINGS")
                            
                            PickerView(title: "Resolution", selection: $resolution)
                            PickerView(title: "FPS", selection: $fps)
                            
                            
                            // Logs
                            if !engine.logs.isEmpty {
                                Text("LOGS")
                                    .font(.caption)
                                    .fontWeight(.bold)
                                    .foregroundColor(.gray)
                                    .padding(.top, 10)
                                
                                ScrollView {
                                    VStack(alignment: .leading, spacing: 4) {
                                        ForEach(engine.logs) { log in
                                            Text(log.message)
                                                .font(.system(size: 10, design: .monospaced))
                                                .foregroundColor(log.type == .error ? .red : (log.type == .success ? .green : .gray))
                                        }
                                    }
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                }
                                .frame(height: 100)
                                .background(Color.black.opacity(0.3))
                                .cornerRadius(8)
                            }
                            
                        }
                        .padding(20)
                    }
                    
                    // Footer
                    VStack {
                        if engine.isProcessing {
                            VStack {
                                ProgressView(value: engine.progress)
                                    .progressViewStyle(LinearProgressViewStyle(tint: .blue))
                                Text("Processing... \(Int(engine.progress * 100))%")
                                    .font(.caption)
                                    .foregroundColor(.white)
                                
                                Button(action: { engine.cancel() }) {
                                    Text("ABORT")
                                        .fontWeight(.bold)
                                        .foregroundColor(.red)
                                        .padding(.top, 5)
                                }
                            }
                            .padding()
                        } else {
                            Button(action: startRender) {
                                Text(engine.logs.last?.type == .success ? "RENDER AGAIN" : "START RENDER")
                                    .font(.headline)
                                    .foregroundColor(.white)
                                    .frame(maxWidth: .infinity)
                                    .frame(height: 50)
                                    .background(Color.blue)
                                    .cornerRadius(8)
                            }
                            .disabled(videoURL == nil)
                            .opacity(videoURL == nil ? 0.5 : 1.0)
                            .padding(20)
                        }
                    }
                    .background(Color(white: 0.12))
                }
            }
            .navigationBarHidden(true)
        }
    }
    
    func startRender() {
        guard let videoURL = videoURL else { return }
        
        let dur = Double(duration) ?? 60.0
        let count = Int(customCount) ?? 5
        
        let settings = ClipJobSettings(
            videoURL: videoURL,
            audioURL: audioURL,
            duration: dur,
            audioMode: audioMode,
            aspectRatio: aspectRatio,
            resolution: resolution,
            fps: fps,
            countMode: countMode,
            customCount: count
        )
        
        Task {
            await engine.processAndExport(settings: settings)
        }
    }
}

// Components

struct SectionHeader: View {
    let title: String
    var body: some View {
        VStack(alignment: .leading) {
            Text(title)
                .font(.system(size: 12, weight: .bold))
                .foregroundColor(.blue)
            Divider().background(Color.gray)
        }
    }
}

struct FileSelector: View {
    let icon: String
    let title: String
    let path: String?
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(.gray)
                VStack(alignment: .leading) {
                    Text(title)
                        .foregroundColor(.gray)
                        .font(.caption)
                    Text(path ?? "Select File...")
                        .foregroundColor(path == nil ? .white.opacity(0.5) : .white)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
                Spacer()
                Image(systemName: "ellipsis")
                    .padding(8)
                    .background(Color(white: 0.2))
                    .cornerRadius(4)
                    .foregroundColor(.white)
            }
            .padding()
            .background(Color(white: 0.15))
            .cornerRadius(8)
        }
    }
}

struct PickerView<T: Hashable & RawRepresentable & Identifiable & CaseIterable>: View where T.RawValue == String {
    let title: String
    @Binding var selection: T
    
    var body: some View {
        VStack(alignment: .leading) {
            Text(title)
                .foregroundColor(.gray)
            
            Menu {
                ForEach(Array(T.allCases)) { option in
                    Button(action: { selection = option }) {
                        Text(option.rawValue)
                        if selection == option { Image(systemName: "checkmark") }
                    }
                }
            } label: {
                HStack {
                    Text(selection.rawValue)
                        .foregroundColor(.white)
                    Spacer()
                    Image(systemName: "chevron.up.chevron.down")
                        .foregroundColor(.gray)
                }
                .padding()
                .background(Color(white: 0.15))
                .cornerRadius(8)
            }
        }
    }
}

// Extension to fix protocol requirement in PickerView
extension CaseIterable where Self: Equatable {
    var allCases: AllCases { Self.allCases }
}
// Actually generic constraints are tricky in SwiftUI structs.
// Let's simplify PickerView to concrete types or standard picker.

extension PickerView where T: CaseIterable {
     init(title: String, selection: Binding<T>) {
         self.title = title
         self._selection = selection
     }
}
