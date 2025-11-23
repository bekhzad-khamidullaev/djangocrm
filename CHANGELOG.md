# Changelog - Admin Theme & SIP Client Redesign

## [2025-11-23] - Major UI Overhaul

### Added
- **New Admin Theme**: Modern Material Design-inspired theme using specified color palette
  - Primary Blue: #4285F4 (RGB 66,133,244)
  - Red Accent: #DB4437 (RGB 219,68,55) 
  - Yellow Accent: #F4B400 (RGB 244,180,0)
  - Green Accent: #0F9D58 (RGB 15,157,88)

- **Theme Controls**:
  - `ADMIN_CUSTOM_THEME = True` setting to enable/disable theme
  - `ADMIN_DENSITY_DEFAULT = 'comfortable'` setting for default density
  - Density toggle button in admin header (comfortable/compact modes)
  - Persistent density selection via localStorage

- **SIP Client Redesign**: Complete iPhone-style phone interface
  - Single-column layout with collapsible settings
  - Large circular call button with phone icon
  - iPhone-style keypad with numbers and letters
  - Compact action buttons (End/Mute/Transfer)
  - Clean, minimalist design matching admin theme

- **Accessibility Improvements**:
  - WCAG-compliant focus rings and contrast ratios
  - prefers-reduced-motion support
  - Touch-friendly button sizes (36px minimum)
  - Skip-to-content link visibility
  - Keyboard navigation enhancements

### Changed
- **File Locations**:
  - Moved SIPml scripts: `wsSipClient/SIPml-*.js` → `voip/static/voip/sipml/`
  - New SIP template: `voip/templates/voip/sipml_client.html`
  - Admin theme: `static/admin/css/styles.css`

- **Admin Header**:
  - Removed BI Analytics button (as requested)
  - Updated SIP button to use Primary Blue color
  - Added density toggle control

### Technical Details
- **CSS Architecture**: Override-based theming preserving Django admin functionality
- **JavaScript**: Clean separation of UI logic (`sipml-ui.js`) and Phone business logic
- **Integration**: `window.SIPML_UI_API` for Phone script integration
- **Responsiveness**: Mobile-first design with proper breakpoints

### Help & Documentation
- Added help fixtures: `help/fixtures/help_theme_sip_en.json` and `help_theme_sip_ru.json`
- Context processor: `common.context_processors.theme.theme`
- URL routing: `/voip/sipml/` for new SIP client

### Migration Notes
- Theme loads conditionally based on `ADMIN_CUSTOM_THEME` setting
- Existing admin functionality preserved through CSS variable system
- SIP client accessible via admin modal and standalone page