// Scarlet Crystal — iOS 26+ system Liquid Glass, with an explicit legacy fallback.
// The earlier opaque UIKit background + painted selection did not establish
// genuine interactive glass. SwiftUI's native GlassEffectContainer now owns
// the tab material, selection morphing and drag response.
// Real iPhone optical/touch verification is a separate release gate.
import SwiftUI
import UIKit

@available(iOS 26.0, *)
private final class SCNativeGlassRimView: UIView {
    private let highlight = CAGradientLayer()
    var rimRadius: CGFloat = 24 {
        didSet { layer.cornerRadius = rimRadius }
    }

    override init(frame: CGRect) {
        super.init(frame: frame)
        isUserInteractionEnabled = false
        backgroundColor = .clear
        layer.cornerRadius = 24
        layer.cornerCurve = .continuous
        layer.borderWidth = 0.7
        layer.borderColor = UIColor.white.withAlphaComponent(0.30).cgColor
        layer.masksToBounds = true
        highlight.colors = [
            UIColor.white.withAlphaComponent(0.19).cgColor,
            UIColor.white.withAlphaComponent(0.025).cgColor,
            UIColor.black.withAlphaComponent(0.045).cgColor
        ]
        highlight.locations = [0, 0.35, 1]
        highlight.startPoint = CGPoint(x: 0.15, y: 0)
        highlight.endPoint = CGPoint(x: 0.85, y: 1)
        layer.addSublayer(highlight)
    }

    required init?(coder: NSCoder) {
        fatalError("SCNativeGlassRimView is programmatic only")
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        highlight.frame = bounds
        CATransaction.commit()
    }

    func select(_ index: Int) {
        guard !UIAccessibility.isReduceMotionEnabled else { return }
        CATransaction.begin()
        CATransaction.setAnimationDuration(0.34)
        highlight.startPoint = CGPoint(x: index == 0 ? 0.15 : 0.85, y: 0)
        CATransaction.commit()
    }
}

/// One native visual effect surface, with the original specular rim.
/// Touch is owned by the single button; material never intercepts hit testing.
struct SCNativeLiquidGlassSurface: UIViewRepresentable {
    var cornerRadius: CGFloat
    var selectedIndex: Int = 0

    func makeUIView(context: Context) -> UIView {
        let container = UIView(frame: .zero)
        container.backgroundColor = .clear
        container.layer.cornerRadius = cornerRadius
        container.layer.cornerCurve = .continuous
        container.clipsToBounds = true
        container.isUserInteractionEnabled = false

        let effect = UIVisualEffectView(frame: .zero)
        if #available(iOS 26.0, *), !UIAccessibility.isReduceTransparencyEnabled {
            let glass = UIGlassEffect(style: .clear)
            glass.isInteractive = true
            effect.effect = glass
        } else {
            effect.effect = UIBlurEffect(style: .systemThinMaterial)
        }
        effect.isUserInteractionEnabled = false
        effect.translatesAutoresizingMaskIntoConstraints = false
        container.addSubview(effect)
        NSLayoutConstraint.activate([
            effect.leadingAnchor.constraint(equalTo: container.leadingAnchor),
            effect.trailingAnchor.constraint(equalTo: container.trailingAnchor),
            effect.topAnchor.constraint(equalTo: container.topAnchor),
            effect.bottomAnchor.constraint(equalTo: container.bottomAnchor)
        ])
        if #available(iOS 26.0, *) {
            let rim = SCNativeGlassRimView(frame: .zero)
            rim.rimRadius = cornerRadius
            rim.accessibilityIdentifier = "SCARLET_ORIGINAL_LIQUID_GLASS_RIM"
            rim.translatesAutoresizingMaskIntoConstraints = false
            container.addSubview(rim)
            NSLayoutConstraint.activate([
                rim.leadingAnchor.constraint(equalTo: container.leadingAnchor),
                rim.trailingAnchor.constraint(equalTo: container.trailingAnchor),
                rim.topAnchor.constraint(equalTo: container.topAnchor),
                rim.bottomAnchor.constraint(equalTo: container.bottomAnchor)
            ])
        }
        return container
    }

    func updateUIView(_ view: UIView, context: Context) {
        view.layer.cornerRadius = cornerRadius
        if #available(iOS 26.0, *) {
            for rim in view.subviews.compactMap({ $0 as? SCNativeGlassRimView }) {
                rim.rimRadius = cornerRadius
                rim.select(selectedIndex)
            }
        }
    }
}

// The upstream LiveContainer target also compiles for iOS 15.0.
// Guard iOS 16-only list background APIs without changing native controls.
extension View {
    @ViewBuilder
    func scarletNativeListTheme() -> some View {
        if #available(iOS 16.0, *) {
            if #available(iOS 26.0, *) {
                self.scrollContentBackground(.hidden)
                    .background(Color(red: 13.0/255, green: 13.0/255, blue: 24.0/255).ignoresSafeArea())
                    .scrollEdgeEffectHidden(true, for: .all)
                    .tint(Color(red: 170.0/255, green: 150.0/255, blue: 1.0))
            } else {
                self.scrollContentBackground(.hidden)
                    .background(Color(red: 13.0/255, green: 13.0/255, blue: 24.0/255).ignoresSafeArea())
                    .tint(Color(red: 170.0/255, green: 150.0/255, blue: 1.0))
            }
        } else {
            self.background(Color(red: 13.0/255, green: 13.0/255, blue: 24.0/255).ignoresSafeArea())
                .tint(Color(red: 170.0/255, green: 150.0/255, blue: 1.0))
        }
    }
}

// The native Form/List scroll view, not its enclosing NavigationView,
// must own enough bottom clearance for the 62pt floating dock plus home area.
extension View {
    @ViewBuilder
    func scarletDockScrollClearance() -> some View {
        if #available(iOS 26.0, *) {
            self.safeAreaInset(edge: .bottom, spacing: 0) {
                Color.clear.frame(height: 140).accessibilityHidden(true)
            }
            .scrollEdgeEffectHidden(true, for: .all)
        } else {
            self.safeAreaInset(edge: .bottom, spacing: 0) {
                Color.clear.frame(height: 140).accessibilityHidden(true)
            }
        }
    }
}

// Settings has a system-managed tab bar on iOS 26+.
// Adding a second 140pt bottom safeAreaInset to the Settings Form created
// an extra ~140pt of maximum scroll travel (the user's second screenshot),
// lifting the version/developer rows too high and leaving a blank footer.
// Keep the upstream Form and the native tabbar as the only inset owners.
// The legacy custom dock needs only enough clearance for its 62pt height.
extension View {
    @ViewBuilder
    func scarletSettingsScrollLimit() -> some View {
        if #available(iOS 26.0, *) {
            self
        } else {
            self.safeAreaInset(edge: .bottom, spacing: 0) {
                Color.clear.frame(height: 72).accessibilityHidden(true)
            }
        }
    }
}

// The nested JIT-Less diagnostics and entitlement pages each own a Form.
// Native iOS 26 TabView protects the navigation-stack safe area; an explicit
// scroll-content margin preserves the last test/help buttons at full scroll.
extension View {
    @ViewBuilder
    func scarletDiagnosticScrollMargins() -> some View {
        if #available(iOS 26.0, *) {
            self.contentMargins(.bottom, 84, for: .scrollContent)
                .scrollEdgeEffectHidden(true, for: .all)
        } else if #available(iOS 17.0, *) {
            self.contentMargins(.bottom, 120, for: .scrollContent)
        } else {
            self.safeAreaInset(edge: .bottom, spacing: 0) {
                Color.clear.frame(height: 120).accessibilityHidden(true)
            }
        }
    }
}

// The actual iOS 26+ implementation uses the SwiftUI glass compositor.
// The OS glass material, not a painted translucent Color, provides refraction.
// The selected segment and the full 62pt dock have distinct compositor
// boundaries so their overlapping shapes don't merge into a flat plate.
// The obsolete SCInteractiveGlassTabs variant was removed to prevent two
// competing custom native-glass implementations in the same host source.
// iOS 26+ main navigation is system TabView; SCInteractiveLiquidGlassTabs
// remains a separate native host adapter and is not layered over TabView.
@available(iOS 26.0, *)
private struct SCInteractiveLiquidGlassTabs: View {
    @Binding var selected: ScarletIndependentShell.Tab
    @Namespace private var selectionNamespace

    private var tabs: [ScarletIndependentShell.Tab] {
        ScarletIndependentShell.Tab.allCases
    }

    private func select(_ tab: ScarletIndependentShell.Tab) {
        guard selected != tab else { return }
        withAnimation(.spring(response: 0.34, dampingFraction: 0.78)) {
            selected = tab
        }
    }

    var body: some View {
        // Only the selected moving capsule is in this compositor; the outer
        // backplate is a separate native Glass surface below.
        GlassEffectContainer(spacing: 6) {
            GeometryReader { geometry in
                HStack(spacing: 6) {
                    ForEach(tabs, id: \.self) { tab in
                        Button {
                            select(tab)
                        } label: {
                            VStack(spacing: 3) {
                                Image(systemName: tab.icon)
                                    .font(.system(size: 19, weight: .medium))
                                Text(tab.rawValue)
                                    .font(.system(size: 11.5, weight: .medium))
                            }
                            .frame(maxWidth: .infinity, minHeight: 52)
                            .foregroundStyle(selected == tab
                                ? Color.white : Color.white.opacity(0.73))
                            .background {
                                if selected == tab {
                                    Capsule()
                                        .glassEffect(
                                            .regular.tint(Color(red: 170.0/255,
                                                                green: 150.0/255,
                                                                blue: 255.0/255).opacity(0.22)).interactive(),
                                            in: .capsule
                                        )
                                        .glassEffectID("selected-tab", in: selectionNamespace)

                                }
                            }
                            .contentShape(Capsule())
                        }
                        .buttonStyle(.plain)
                        .frame(maxWidth: .infinity)
                        .accessibilityIdentifier("SCARLET_NATIVE_GLASS_TAB_" + tab.rawValue)
                        .accessibilityAddTraits(selected == tab ? .isSelected : [])
                    }
                }
                .padding(.horizontal, 5)
                .frame(height: 62)
                // Drag previews move the selected system-glass capsule across
                // the four real buttons; these are not duplicate touch routes.
                .simultaneousGesture(
                    DragGesture(minimumDistance: 8)
                        .onChanged { value in
                            let width = max(1, geometry.size.width)
                            let fraction = min(max(value.location.x / width, 0), 0.999)
                            let index = min(tabs.count - 1, Int(fraction * CGFloat(tabs.count)))
                            select(tabs[index])
                        }
                )
            }
        }
        .frame(height: 62)
        // A separate system-glass backplate avoids merging the moving
        // selection pill into its fully overlapping parent glass surface.
        // Neither surface is an opaque painted replacement.
        .background {
            Capsule()
                .glassEffect(.regular.interactive(), in: .capsule)
                .overlay {
                    Capsule()
                        .strokeBorder(
                            LinearGradient(colors: [
                                Color.white.opacity(0.50),
                                Color(red: 217.0/255, green: 210.0/255,
                                      blue: 248.0/255).opacity(0.30),
                                Color.white.opacity(0.07),
                                Color.white.opacity(0.38)
                            ], startPoint: .topLeading, endPoint: .bottomTrailing),
                            lineWidth: 1.2
                        )
                        .allowsHitTesting(false)
                }
                .accessibilityIdentifier("SCARLET_LIVE_GLASS_BAR_MATERIAL")
        }
        .onAppear {
            // This indicates the native rendering branch was mounted, not
            // proof that GPU optical rendering was observed on a real device.
            ScarletDiagnosticRecorder.shared.record("glass", "native_path_selected",
                fields: ["api": "SwiftUI.GlassEffectContainer",
                         "interactive": "true", "slots": "4"])
        }
    }
}

@available(iOS 16.0, *)
struct ScarletNativeGlassTabBar: View {
    @Binding var selected: ScarletIndependentShell.Tab

    var body: some View {
        Group {
            if #available(iOS 26.0, *),
               !UIAccessibility.isReduceTransparencyEnabled {
                // Real native Liquid Glass interaction, not a static gray
                // capsule backed by a blur or tinted foreground overlay.
                SCInteractiveLiquidGlassTabs(selected: $selected)
            } else {
                // Explicit accessibility / pre-iOS26 fallback; never call it
                // native Liquid Glass.
                HStack(spacing: 6) {
                    ForEach(ScarletIndependentShell.Tab.allCases, id: \.self) { tab in
                        Button { selected = tab } label: {
                            VStack(spacing: 3) {
                                Image(systemName: tab.icon)
                                    .font(.system(size: 19, weight: .medium))
                                Text(tab.rawValue)
                                    .font(.system(size: 11.5, weight: .medium))
                            }
                            .frame(maxWidth: .infinity, minHeight: 52)
                            .foregroundStyle(selected == tab
                                ? Color.white : Color.white.opacity(0.73))
                            .background(selected == tab
                                ? Color.white.opacity(0.16) : Color.clear, in: Capsule())
                        }
                        .buttonStyle(.plain)
                        .frame(maxWidth: .infinity)
                        .accessibilityIdentifier("SCARLET_NATIVE_GLASS_TAB_" + tab.rawValue)
                    }
                }
                .padding(.horizontal, 5)
                .frame(height: 62)
                .background {
                    SCNativeLiquidGlassSurface(cornerRadius: 31)
                }
            }
        }
        .frame(height: 62)
    }
}

struct ScarletNativeGlassSwitcher: View {
    let openManager: () -> Void

    var body: some View {
        Button(action: openManager) {
            Image(systemName: "square.on.square")
                .font(.system(size: 22, weight: .semibold))
                .foregroundStyle(.white)
                .frame(width: 62, height: 62)
                .background {
                    if #available(iOS 26.0, *),
                       !UIAccessibility.isReduceTransparencyEnabled {
                        Circle()
                            .glassEffect(.regular.interactive(), in: .circle)
                            .accessibilityIdentifier("SCARLET_LIVE_GLASS_SWITCHER_MATERIAL")
                    } else {
                        SCNativeLiquidGlassSurface(cornerRadius: 31)
                            .clipShape(Circle())
                    }
                }
                .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .onLongPressGesture(minimumDuration: 0.38, perform: openManager)
        .accessibilityIdentifier("SCARLET_NATIVE_GLASS_SINGLE_APP_SWITCHER")
    }
}
