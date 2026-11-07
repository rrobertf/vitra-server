import UIKit
import WebKit

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?
    func application(_ application: UIApplication, didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        let window = UIWindow(frame: UIScreen.main.bounds)
        window.rootViewController = VitraViewController()
        window.overrideUserInterfaceStyle = .dark
        window.makeKeyAndVisible()
        self.window = window
        return true
    }
}

final class VitraViewController: UIViewController, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
    private var webView: WKWebView!
    private var addressField = UITextField()
    private var setupView = UIStackView()
    private let indicator = UIActivityIndicatorView(style: .large)
    private var destination: URL?
    private var currentURL: URL?

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(red: 0.04, green: 0.05, blue: 0.06, alpha: 1)
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.allowsInlineMediaPlayback = true
        configuration.allowsAirPlayForMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = .audio
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.isOpaque = false
        webView.backgroundColor = view.backgroundColor
        webView.scrollView.backgroundColor = view.backgroundColor
        webView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(webView)
        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: view.topAnchor),
            webView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor)
        ])
        configureSetup()
        indicator.translatesAutoresizingMaskIntoConstraints = false
        indicator.hidesWhenStopped = true
        view.addSubview(indicator)
        NSLayoutConstraint.activate([
            indicator.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            indicator.centerYAnchor.constraint(equalTo: view.centerYAnchor)
        ])
        if let saved = UserDefaults.standard.string(forKey: "vitra.serverURL"), let url = validServer(saved) {
            load(url)
        } else { showSetup() }
    }

    private func validServer(_ value: String) -> URL? {
        guard var parts = URLComponents(string: value.trimmingCharacters(in: .whitespacesAndNewlines)),
              parts.scheme?.lowercased() == "https", let host = parts.host, !host.isEmpty,
              host != "localhost", host != "127.0.0.1", host != "::1",
              parts.user == nil, parts.password == nil, parts.query == nil, parts.fragment == nil,
              parts.path.isEmpty || parts.path == "/" else { return nil }
        parts.path = "/"
        return parts.url
    }

    private func configureSetup() {
        let title = UILabel()
        title.text = "VITRA"
        title.font = .systemFont(ofSize: 34, weight: .semibold)
        title.textAlignment = .center
        let message = UILabel()
        message.text = "Tu música, tu espacio.\nConecta tu servidor de Vitra para comenzar."
        message.font = .systemFont(ofSize: 15)
        message.textColor = .secondaryLabel
        message.textAlignment = .center
        message.numberOfLines = 0
        addressField.placeholder = "https://tu-servidor.onrender.com"
        addressField.keyboardType = .URL
        addressField.autocapitalizationType = .none
        addressField.autocorrectionType = .no
        addressField.borderStyle = .roundedRect
        addressField.accessibilityLabel = "Dirección HTTPS del servidor de Vitra"
        addressField.text = UserDefaults.standard.string(forKey: "vitra.serverURL")
        let connect = UIButton(type: .system)
        var style = UIButton.Configuration.filled()
        style.title = "Abrir Vitra"
        style.baseBackgroundColor = UIColor(white: 0.9, alpha: 1)
        style.baseForegroundColor = .black
        style.cornerStyle = .capsule
        connect.configuration = style
        connect.addTarget(self, action: #selector(connectServer), for: .touchUpInside)
        setupView = UIStackView(arrangedSubviews: [title, message, addressField, connect])
        setupView.axis = .vertical
        setupView.spacing = 22
        setupView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(setupView)
        NSLayoutConstraint.activate([
            setupView.centerYAnchor.constraint(equalTo: view.safeAreaLayoutGuide.centerYAnchor),
            setupView.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            setupView.widthAnchor.constraint(lessThanOrEqualToConstant: 400),
            setupView.leadingAnchor.constraint(greaterThanOrEqualTo: view.leadingAnchor, constant: 28),
            setupView.trailingAnchor.constraint(lessThanOrEqualTo: view.trailingAnchor, constant: -28),
            addressField.heightAnchor.constraint(equalToConstant: 48)
        ])
    }

    @objc private func connectServer() {
        guard let url = validServer(addressField.text ?? "") else {
            showMessage("Dirección no válida", "Introduce la dirección HTTPS de tu servidor, sin rutas ni credenciales. La dirección 127.0.0.1 de tu PC no funciona desde el iPhone.")
            return
        }
        view.endEditing(true)
        UserDefaults.standard.set(url.absoluteString, forKey: "vitra.serverURL")
        load(url)
    }

    private func load(_ url: URL) {
        currentURL = url
        setupView.isHidden = true
        webView.isHidden = false
        indicator.startAnimating()
        webView.load(URLRequest(url: url))
    }
    private func showSetup() {
        indicator.stopAnimating()
        webView.isHidden = true
        setupView.isHidden = false
    }
    private func showMessage(_ title: String, _ text: String) {
        let alert = UIAlertController(title: title, message: text, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Aceptar", style: .default))
        present(alert, animated: true)
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { indicator.stopAnimating() }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        guard (error as NSError).code != NSURLErrorCancelled else { return }
        showSetup()
        showMessage("No se pudo abrir Vitra", "Comprueba el servidor y la conexión. Tus datos locales no se han borrado.")
    }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        indicator.stopAnimating()
    }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { webView.reload() }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if action.shouldPerformDownload { decisionHandler(.download); return }
        guard let url = action.request.url else { decisionHandler(.cancel); return }
        if url.scheme == "blob" || url.absoluteString == "about:blank" { decisionHandler(.allow); return }
        guard url.scheme == "https" else { decisionHandler(.cancel); return }
        if action.navigationType == .linkActivated, let current = currentURL, url.host != current.host {
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
        } else { decisionHandler(.allow) }
    }
    func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        decisionHandler(response.canShowMIMEType ? .allow : .download)
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url, url.scheme == "https" { UIApplication.shared.open(url) }
        return nil
    }
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let alert = UIAlertController(title: "Vitra", message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Aceptar", style: .default) { _ in completionHandler() })
        present(alert, animated: true)
    }
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let alert = UIAlertController(title: "Vitra", message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel) { _ in completionHandler(false) })
        alert.addAction(UIAlertAction(title: "Continuar", style: .default) { _ in completionHandler(true) })
        present(alert, animated: true)
    }
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { download.delegate = self }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        do {
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            let file = folder.appendingPathComponent(URL(fileURLWithPath: suggestedFilename).lastPathComponent)
            destination = file
            completionHandler(file)
        } catch { completionHandler(nil) }
    }
    func downloadDidFinish(_ download: WKDownload) {
        guard let destination else { return }
        let share = UIActivityViewController(activityItems: [destination], applicationActivities: nil)
        share.popoverPresentationController?.sourceView = view
        share.popoverPresentationController?.sourceRect = CGRect(x: view.bounds.midX, y: view.bounds.midY, width: 1, height: 1)
        present(share, animated: true)
    }
    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        showMessage("No se pudo guardar el archivo", "Vuelve a crear la copia desde Configuración.")
    }
}
