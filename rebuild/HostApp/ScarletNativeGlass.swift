// Scarlet Crystal — source-derived native UIKit Liquid Glass adapter.
// Optical values and native UIGlassEffect are derived from the protected
// pre-rebuild V131 implementation. No legacy V-series patch stack is applied.
// Actual touch/morph/rotation acceptance requires an installed iPhone build.
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

struct ScarletNativeGlassTabBar: View {
    @Binding var selected: ScarletIndependentShell.Tab

    var body: some View {
        HStack(spacing: 6) {
            ForEach(ScarletIndependentShell.Tab.allCases, id: \.self) { tab in
                Button {
                    selected = tab
                } label: {
                    VStack(spacing: 3) {
                        Image(systemName: tab.icon)
                            .font(.system(size: 19, weight: .medium))
                        Text(tab.rawValue)
                            .font(.system(size: 11.5, weight: .medium))
                    }
                    .frame(maxWidth: .infinity, minHeight: 52)
                    .foregroundStyle(selected == tab ? Color.white : Color.white.opacity(0.73))
                    .background(selected == tab ? Color.white.opacity(0.16) : Color.clear,
                                in: Capsule())
                }
                .buttonStyle(.plain)
                .frame(maxWidth: .infinity)
                .accessibilityIdentifier("SCARLET_NATIVE_GLASS_TAB_" + tab.rawValue)
                .accessibilityAddTraits(selected == tab ? .isSelected : [])
            }
        }
        .padding(.horizontal, 5)
        .frame(height: 62)
        .background {
            SCNativeLiquidGlassSurface(cornerRadius: 31,
                 selectedIndex: ScarletIndependentShell.Tab.allCases.firstIndex(of: selected) ?? 0)
        }
        .clipShape(Capsule())
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
                    SCNativeLiquidGlassSurface(cornerRadius: 31)
                }
                .clipShape(Circle())
                .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .onLongPressGesture(minimumDuration: 0.38, perform: openManager)
        .accessibilityIdentifier("SCARLET_NATIVE_GLASS_SINGLE_APP_SWITCHER")
    }
}
