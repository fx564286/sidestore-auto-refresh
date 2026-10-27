#!/usr/bin/env python3
"""V131: translate the user's four-layer web Liquid Glass reference to UIKit.

Apply after V129. Keep exactly one glass-backed UIKit guest picker; do not
introduce parallel menu windows, webviews, self-installed app services,
guest JIT modifications, or any code touching signing/pairing data.
"""
from pathlib import Path
import sys

DOCK = Path("MultitaskSupport/MultitaskDockView.swift")
MARK = "SCARLET_V131_REFERENCE_LIQUID_GLASS"

def one(s: str, old: str, new: str, label: str) -> str:
    count = s.count(old)
    if count != 1:
        raise ValueError(f"V131 {label}: expected one anchor, observed {count}")
    return s.replace(old, new, 1)

RIM = '''// SCARLET_V131_REFERENCE_LIQUID_GLASS: Apple's native UIGlassEffect
// provides refraction. This lightweight highlight-only layer provides
// the subtle Fresnel rim/specular sweep from the supplied web reference.
// Do not simulate refraction with a second expensive background blur.
@available(iOS 26.0, *)
private final class SCNativeGlassRimView: UIView {
    private let highlight = CAGradientLayer()

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

'''

def transform(s: str) -> str:
    if MARK in s:
        if s.count(MARK) != 1 or 'SCNativeGlassRimView' not in s:
            raise ValueError("V131 incomplete/duplicate")
        return s
    for required in ("SCARLET_V129_PICKER_RESILIENCE", "SCARLET_V127_COMPLETE_GLASS",
                     "SCARLET_V126_INPLACE_TAB_CONTENT", "SCARLET_V129_GLASS"):
        if required not in s:
            raise ValueError(f"V131 prerequisite missing: {required}")
    s = one(s, "import Combine\n", "import Combine\n\n"+RIM, "single rim class")
    s = one(s,
        '''        // SCARLET_V125_NATIVE_GLASS: native iOS glass; accessible fallback.
        let material = UIVisualEffectView(effect: UIBlurEffect(style: .systemMaterial))
        if #available(iOS 26.0, *), !UIAccessibility.isReduceTransparencyEnabled {
            material.effect = UIGlassEffect()
            NSLog("[SCARLET_V129_GLASS] picker=native_UIGlassEffect reduceTransparency=0")
        }''',
        '''        // V131: native iOS glass does the refraction. The user's four
        // optical layers inform the edge highlight, not four stacked blurs.
        let material = UIVisualEffectView(effect: UIBlurEffect(style: .systemMaterial))
        if #available(iOS 26.0, *), !UIAccessibility.isReduceTransparencyEnabled {
            let glass = UIGlassEffect(style: .clear)
            glass.isInteractive = true
            material.effect = glass
            NSLog("[SCARLET_V129_GLASS] picker=native_UIGlassEffect reduceTransparency=0")
            NSLog("[SCARLET_V131_GLASS] panel=clear interactive=1 rim=fresnel native=1")
        }''',
        "actual clear native glass effect")
    s = one(s,
        '''        overlay.addSubview(material)

        let content = UIStackView()''',
        '''        overlay.addSubview(material)
        if #available(iOS 26.0, *), !UIAccessibility.isReduceTransparencyEnabled {
            let opticalRim = SCNativeGlassRimView()
            opticalRim.translatesAutoresizingMaskIntoConstraints = false
            material.contentView.addSubview(opticalRim)
            NSLayoutConstraint.activate([
                opticalRim.leadingAnchor.constraint(equalTo: material.contentView.leadingAnchor),
                opticalRim.trailingAnchor.constraint(equalTo: material.contentView.trailingAnchor),
                opticalRim.topAnchor.constraint(equalTo: material.contentView.topAnchor),
                opticalRim.bottomAnchor.constraint(equalTo: material.contentView.bottomAnchor)
            ])
        }

        let content = UIStackView()''',
        "one nonintercepting Fresnel optical layer")
    s = one(s,
        '''            let tabGlass = UIVisualEffectView(effect: UIGlassEffect())
            tabGlass.accessibilityIdentifier = "scarlet.v127.glass.tabs"
            tabGlass.isUserInteractionEnabled = false
            tabGlass.translatesAutoresizingMaskIntoConstraints = false
            tabGlass.layer.cornerRadius = 20
            tabGlass.clipsToBounds = true
            tabHousing.insertSubview(tabGlass, belowSubview: tabPicker)
            NSLayoutConstraint.activate([
                tabGlass.leadingAnchor.constraint(equalTo: tabHousing.leadingAnchor),
                tabGlass.trailingAnchor.constraint(equalTo: tabHousing.trailingAnchor),
                tabGlass.topAnchor.constraint(equalTo: tabHousing.topAnchor),
                tabGlass.bottomAnchor.constraint(equalTo: tabHousing.bottomAnchor)
            ])
            tabPicker.backgroundColor = .clear
            tabPicker.selectedSegmentTintColor = .tertiarySystemFill
            tabPicker.setBackgroundImage(UIImage(), for: .normal, barMetrics: .default)''',
        '''            // Remove the second blur/glass sampling pass on top of the
            // single clear-glass panel. Glass container interaction is owned
            // by the panel, not duplicated per nested control.
            let tabRim = SCNativeGlassRimView()
            tabRim.accessibilityIdentifier = "scarlet.v127.glass.tabs"
            tabRim.translatesAutoresizingMaskIntoConstraints = false
            tabRim.layer.cornerRadius = 20
            tabHousing.insertSubview(tabRim, belowSubview: tabPicker)
            NSLayoutConstraint.activate([
                tabRim.leadingAnchor.constraint(equalTo: tabHousing.leadingAnchor),
                tabRim.trailingAnchor.constraint(equalTo: tabHousing.trailingAnchor),
                tabRim.topAnchor.constraint(equalTo: tabHousing.topAnchor),
                tabRim.bottomAnchor.constraint(equalTo: tabHousing.bottomAnchor)
            ])
            tabPicker.backgroundColor = UIColor.white.withAlphaComponent(0.04)
            tabPicker.selectedSegmentTintColor = UIColor.white.withAlphaComponent(0.26)
            tabPicker.setBackgroundImage(UIImage(), for: .normal, barMetrics: .default)''',
        "remove nested glass while retaining V127 test marker")
    # Replace all three row backing effects with a *single* glass panel.
    # Preserve indentation in the window-actions sub-block.
    import re
    pattern = re.compile(
        r"(?m)^( +)if #available\(iOS 26\.0, \*\), !UIAccessibility\.isReduceTransparencyEnabled \{\n"
        r"\1    var config = UIButton\.Configuration\.glass\(\)\n"
        r"\1    config\.baseForegroundColor = \.label\n"
        r"\1    config\.cornerStyle = \.medium\n"
        r"\1    item\.configuration = config\n"
        r"\1    item\.backgroundColor = \.clear\n"
        r"\1\} else \{\n"
        r"\1    item\.backgroundColor = UIColor\.secondarySystemGroupedBackground\n"
        r"\1\}"
    )
    def row(m):
        ind=m.group(1)
        return (ind+"if #available(iOS 26.0, *), !UIAccessibility.isReduceTransparencyEnabled {\n"
                +ind+"    // The panel owns Liquid Glass; rows remain translucent controls.\n"
                +ind+"    item.configuration = .plain()\n"
                +ind+"    item.backgroundColor = UIColor.white.withAlphaComponent(0.10)\n"
                +ind+"    item.layer.borderColor = UIColor.white.withAlphaComponent(0.23).cgColor\n"
                +ind+"    item.layer.borderWidth = 0.55\n"
                +ind+"    item.layer.cornerCurve = .continuous\n"
                +ind+"} else {\n"
                +ind+"    item.backgroundColor = UIColor.secondarySystemGroupedBackground\n"
                +ind+"}")
    s,n=pattern.subn(row,s)
    if n != 2:
        raise ValueError(f"V131 regular row source count: {n}")
    # V129's third window action block had noncanonical indentation.
    # Replace that exact legacy fragment and restore normal indentation.
    malformed = """                if #available(iOS 26.0, *), !UIAccessibility.isReduceTransparencyEnabled {
                var config = UIButton.Configuration.glass()
                config.baseForegroundColor = .label
                config.cornerStyle = .medium
                item.configuration = config
                item.backgroundColor = .clear
            } else {
                item.backgroundColor = UIColor.secondarySystemGroupedBackground
            }"""
    proper = """                if #available(iOS 26.0, *), !UIAccessibility.isReduceTransparencyEnabled {
                    item.configuration = .plain()
                    item.backgroundColor = UIColor.white.withAlphaComponent(0.10)
                    item.layer.borderColor = UIColor.white.withAlphaComponent(0.23).cgColor
                    item.layer.borderWidth = 0.55
                    item.layer.cornerCurve = .continuous
                } else {
                    item.backgroundColor = UIColor.secondarySystemGroupedBackground
                }"""
    s = one(s, malformed, proper, "third window-action row")
    # Keep the tab housing weak to avoid UIControl -> action -> view cycles.
    s = one(s,
        "tabPicker.addAction(UIAction { [weak self, weak tabPicker, weak overlay] _ in",
        "tabPicker.addAction(UIAction { [weak self, weak tabPicker, weak overlay, weak tabHousing] _ in",
        "weak tab housing in UIAction")
    # Keep tab selection gesture native but move the specular rim gently.
    needle = '''            let targetWindowActions = tabPicker.selectedSegmentIndex == 1'''
    s=one(s,needle,
        needle+'''
            if #available(iOS 26.0, *),
               let tabHousing,
               let rim = tabHousing.subviews.first(where: { $0 is SCNativeGlassRimView }) as? SCNativeGlassRimView {
                rim.select(tabPicker.selectedSegmentIndex)
            }''',
        "light follows tab selection")
    return s

def apply(root: Path):
    path=root/DOCK
    if not path.is_file() or path.is_symlink():
        raise ValueError("V131 source absent")
    a=path.read_text()
    b=transform(a)
    if transform(b)!=b:
        raise ValueError("V131 non-idempotent")
    if a!=b:path.write_text(b)
    print("[PASS] V131 native clear Liquid Glass + lightweight Fresnel rim + one panel")

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: patch_v131_reference_liquid_glass.py <LiveContainer source>")
    apply(Path(sys.argv[1]))
