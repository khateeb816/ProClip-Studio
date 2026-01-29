import SwiftUI
import UIKit
import UniformTypeIdentifiers

struct AudioPicker: UIViewControllerRepresentable {
    @Binding var selectedURL: URL?
    
    func makeUIViewController(context: Context) -> UIDocumentPickerViewController {
        let types: [UTType] = [.audio, .mp3]
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: types)
        picker.delegate = context.coordinator
        picker.allowsMultipleSelection = false
        return picker
    }
    
    func updateUIViewController(_ uiViewController: UIDocumentPickerViewController, context: Context) {}
    
    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }
    
    class Coordinator: NSObject, UIDocumentPickerDelegate {
        let parent: AudioPicker
        
        init(_ parent: AudioPicker) {
            self.parent = parent
        }
        
        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            guard let url = urls.first else { return }
            
            // Security scoped resource? iOS usually handles this for open, but copy is safer for processing
            let startAccess = url.startAccessingSecurityScopedResource()
            
            defer {
                if startAccess { url.stopAccessingSecurityScopedResource() }
            }
            
            let tempDir = FileManager.default.temporaryDirectory
            let fileName = "bg_audio_\(Date().timeIntervalSince1970).\(url.pathExtension)"
            let dstURL = tempDir.appendingPathComponent(fileName)
            
            do {
                try? FileManager.default.removeItem(at: dstURL)
                try FileManager.default.copyItem(at: url, to: dstURL)
                DispatchQueue.main.async {
                    self.parent.selectedURL = dstURL
                }
            } catch {
                print("Error copying file: \(error)")
            }
        }
    }
}
