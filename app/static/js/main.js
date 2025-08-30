// Global variables
let currentLanguage = 'en';
let translations = {};
let userSettings = {};

// Make variables globally accessible
window.currentLanguage = currentLanguage;
window.translations = translations;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    // Load saved language from localStorage
    const savedLanguage = localStorage.getItem('aivideo_language') || 'en';
    currentLanguage = savedLanguage;
    
    loadLanguage(currentLanguage);
    loadUserSettings();
    initializeEventListeners();
    setupFileUploads();
});

// Load language translations
async function loadLanguage(lang) {
    try {
        const response = await fetch(`/api/translations/${lang}`);
        translations = await response.json();
        window.translations = translations; // Update global reference
        currentLanguage = lang;
        window.currentLanguage = currentLanguage; // Update global reference
        
        // Apply translations immediately and again after a small delay
        updateUI();
        setTimeout(() => updateUI(), 50);
        
        // Update language display with flag
        const flagElement = document.getElementById('current-flag');
        const langElement = document.getElementById('current-lang');
        
        if (lang === 'en') {
            flagElement.textContent = '🇺🇸';
            langElement.textContent = 'English';
        } else {
            flagElement.textContent = '🇮🇹';
            langElement.textContent = 'Italiano';
        }
    } catch (error) {
        console.error('Error loading translations:', error);
    }
}

// Change language
function changeLanguage(lang) {
    // Save language choice in localStorage
    localStorage.setItem('aivideo_language', lang);
    currentLanguage = lang;
    
    loadLanguage(lang);
    saveUserSettings();
}

// Update UI with current language  
function updateUI() {
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');
        const translation = getTranslation(key);
        if (translation) {
            element.textContent = translation;
        }
    });
    
    // Update placeholders
    document.querySelectorAll('[data-placeholder-i18n]').forEach(element => {
        const key = element.getAttribute('data-placeholder-i18n');
        const translation = getTranslation(key);
        if (translation) {
            element.placeholder = translation;
        }
    });
}

// Make updateUI globally accessible
window.updateUI = updateUI;

// Get translation by key
function getTranslation(key) {
    const keys = key.split('.');
    let translation = translations;
    
    for (const k of keys) {
        if (translation && translation[k]) {
            translation = translation[k];
        } else {
            return key;
        }
    }
    
    return translation;
}

// Load user settings
async function loadUserSettings() {
    try {
        const response = await fetch('/api/settings');
        if (response.ok) {
            userSettings = await response.json();
            applySettings();
        }
    } catch (error) {
        console.error('Error loading settings:', error);
        userSettings = getDefaultSettings();
    }
}

// Save user settings
async function saveUserSettings() {
    try {
        userSettings.language = currentLanguage;
        await fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(userSettings)
        });
    } catch (error) {
        console.error('Error saving settings:', error);
    }
}

// Get default settings
function getDefaultSettings() {
    return {
        language: 'en',
        video_settings: {
            logo_overlay: false,
            cta_overlay: false,
            transcription: false,
            translation: false,
            thumbnail_generation: false,
            metadata_generation: false,
            youtube_upload: false
        },
        logo_settings: {
            position: 'top_right',
            size: 10,
            start_time: 0.0,
            end_time: null
        },
        cta_settings: {
            position: 'bottom_right',
            size: 20,
            start_time: 0.0,
            end_time: null,
            chroma_key: false,
            chroma_color: '#00ff00'
        },
        thumbnail_settings: {
            auto_generate: true,
            custom_text: '',
            font_size: 48,
            text_color: '#ffffff',
            custom_images: []
        },
        metadata_settings: {
            auto_generate: true,
            global_words: [],
            global_hashtags: [],
            global_tags: []
        },
        youtube_settings: {
            connected: false,
            channel_id: null,
            privacy: 'private',
            category: '22'
        },
        file_output_settings: {
            save_video: true,
            save_original_transcript: true,
            save_translated_transcript: true,
            save_original_subtitles: true,
            save_translated_subtitles: true,
            save_translated_audio: false
        }
    };
}

// Apply settings to UI
function applySettings() {
    // Apply feature toggles
    Object.entries(userSettings.video_settings || {}).forEach(([key, value]) => {
        const toggle = document.getElementById(key.replace('_', ''));
        if (toggle) {
            toggle.checked = value;
        }
    });

    // Apply logo settings
    if (userSettings.logo_settings) {
        const logoPos = document.getElementById('logoPosition');
        const logoSize = document.getElementById('logoSize');
        const logoStart = document.getElementById('logoStartTime');
        const logoEnd = document.getElementById('logoEndTime');
        
        if (logoPos) logoPos.value = userSettings.logo_settings.position;
        if (logoSize) {
            logoSize.value = userSettings.logo_settings.size;
            document.getElementById('logoSizeValue').textContent = userSettings.logo_settings.size;
        }
        if (logoStart) logoStart.value = userSettings.logo_settings.start_time;
        if (logoEnd && userSettings.logo_settings.end_time) {
            logoEnd.value = userSettings.logo_settings.end_time;
        }
    }

    // Apply CTA settings
    if (userSettings.cta_settings) {
        const ctaPos = document.getElementById('ctaPosition');
        const ctaSize = document.getElementById('ctaSize');
        const ctaStart = document.getElementById('ctaStartTime');
        const ctaEnd = document.getElementById('ctaEndTime');
        const ctaChroma = document.getElementById('ctaChromaKey');
        
        if (ctaPos) ctaPos.value = userSettings.cta_settings.position;
        if (ctaSize) {
            ctaSize.value = userSettings.cta_settings.size;
            document.getElementById('ctaSizeValue').textContent = userSettings.cta_settings.size;
        }
        if (ctaStart) ctaStart.value = userSettings.cta_settings.start_time;
        if (ctaEnd && userSettings.cta_settings.end_time) {
            ctaEnd.value = userSettings.cta_settings.end_time;
        }
        if (ctaChroma) ctaChroma.checked = userSettings.cta_settings.chroma_key;
    }

    // Apply thumbnail settings
    if (userSettings.thumbnail_settings) {
        const autoThumb = document.getElementById('autoThumbnail');
        const thumbText = document.getElementById('thumbnailText');
        const thumbFontSize = document.getElementById('thumbnailFontSize');
        const thumbTextColor = document.getElementById('thumbnailTextColor');
        
        if (autoThumb) autoThumb.checked = userSettings.thumbnail_settings.auto_generate;
        if (thumbText) thumbText.value = userSettings.thumbnail_settings.custom_text;
        if (thumbFontSize) {
            thumbFontSize.value = userSettings.thumbnail_settings.font_size;
            document.getElementById('thumbnailFontSizeValue').textContent = userSettings.thumbnail_settings.font_size;
        }
        if (thumbTextColor) thumbTextColor.value = userSettings.thumbnail_settings.text_color;
    }

    // Apply metadata settings
    if (userSettings.metadata_settings) {
        const autoMeta = document.getElementById('autoMetadata');
        const globalWords = document.getElementById('globalWords');
        
        if (autoMeta) autoMeta.checked = userSettings.metadata_settings.auto_generate;
        if (globalWords) globalWords.value = userSettings.metadata_settings.global_words.join(', ');
    }

    // Apply YouTube settings
    if (userSettings.youtube_settings) {
        const youtubePrivacy = document.getElementById('youtubePrivacy');
        const youtubeCategory = document.getElementById('youtubeCategory');
        
        if (youtubePrivacy) youtubePrivacy.value = userSettings.youtube_settings.privacy;
        if (youtubeCategory) youtubeCategory.value = userSettings.youtube_settings.category;
        
        if (userSettings.youtube_settings.connected) {
            showYouTubeConnected(userSettings.youtube_settings.channel_name || 'Your Channel');
        }
    }
    
    // Apply output file settings
    if (userSettings.file_output_settings) {
        const saveVideo = document.getElementById('saveVideo');
        const saveOriginalTranscript = document.getElementById('saveOriginalTranscript');
        const saveTranslatedTranscript = document.getElementById('saveTranslatedTranscript');
        const saveOriginalSubtitles = document.getElementById('saveOriginalSubtitles');
        const saveTranslatedSubtitles = document.getElementById('saveTranslatedSubtitles');
        const saveTranslatedAudio = document.getElementById('saveTranslatedAudio');
        
        if (saveVideo) saveVideo.checked = userSettings.file_output_settings.save_video;
        if (saveOriginalTranscript) saveOriginalTranscript.checked = userSettings.file_output_settings.save_original_transcript;
        if (saveTranslatedTranscript) saveTranslatedTranscript.checked = userSettings.file_output_settings.save_translated_transcript;
        if (saveOriginalSubtitles) saveOriginalSubtitles.checked = userSettings.file_output_settings.save_original_subtitles;
        if (saveTranslatedSubtitles) saveTranslatedSubtitles.checked = userSettings.file_output_settings.save_translated_subtitles;
        if (saveTranslatedAudio) saveTranslatedAudio.checked = userSettings.file_output_settings.save_translated_audio;
    }
}

// Initialize event listeners
function initializeEventListeners() {
    // Feature toggles
    document.querySelectorAll('.feature-toggle').forEach(toggle => {
        toggle.addEventListener('change', function() {
            const feature = this.getAttribute('data-feature');
            if (!userSettings.video_settings) userSettings.video_settings = {};
            userSettings.video_settings[feature] = this.checked;
            saveUserSettings();
        });
    });

    // Range sliders
    document.getElementById('logoSize').addEventListener('input', function() {
        document.getElementById('logoSizeValue').textContent = this.value;
        if (!userSettings.logo_settings) userSettings.logo_settings = {};
        userSettings.logo_settings.size = parseInt(this.value);
        saveUserSettings();
    });

    document.getElementById('ctaSize').addEventListener('input', function() {
        document.getElementById('ctaSizeValue').textContent = this.value;
        if (!userSettings.cta_settings) userSettings.cta_settings = {};
        userSettings.cta_settings.size = parseInt(this.value);
        saveUserSettings();
    });

    document.getElementById('thumbnailFontSize').addEventListener('input', function() {
        document.getElementById('thumbnailFontSizeValue').textContent = this.value;
        if (!userSettings.thumbnail_settings) userSettings.thumbnail_settings = {};
        userSettings.thumbnail_settings.font_size = parseInt(this.value);
        saveUserSettings();
        updateThumbnailPreview();
    });

    // Settings change listeners
    ['logoPosition', 'logoStartTime', 'logoEndTime'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('change', function() {
                if (!userSettings.logo_settings) userSettings.logo_settings = {};
                const key = id.replace('logo', '').replace(/([A-Z])/g, '_$1').toLowerCase().substring(1);
                userSettings.logo_settings[key] = this.value;
                saveUserSettings();
            });
        }
    });

    ['ctaPosition', 'ctaStartTime', 'ctaEndTime', 'ctaChromaKey'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('change', function() {
                if (!userSettings.cta_settings) userSettings.cta_settings = {};
                const key = id.replace('cta', '').replace(/([A-Z])/g, '_$1').toLowerCase().substring(1);
                userSettings.cta_settings[key] = element.type === 'checkbox' ? this.checked : this.value;
                saveUserSettings();
            });
        }
    });

    // Thumbnail settings
    ['autoThumbnail', 'thumbnailText', 'thumbnailTextColor'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('change', function() {
                if (!userSettings.thumbnail_settings) userSettings.thumbnail_settings = {};
                const key = id.replace('thumbnail', '').replace(/([A-Z])/g, '_$1').toLowerCase().substring(1);
                if (key === 'auto') key = 'auto_generate';
                if (key === 'text') key = 'custom_text';
                if (key === 'text_color') key = 'text_color';
                userSettings.thumbnail_settings[key] = element.type === 'checkbox' ? this.checked : this.value;
                saveUserSettings();
                updateThumbnailPreview();
            });
        }
    });

    // YouTube connection
    document.getElementById('connectYouTube').addEventListener('click', connectToYouTube);
    document.getElementById('disconnectYouTube').addEventListener('click', disconnectFromYouTube);

    // Audio translation settings
    ['originalLanguage', 'targetLanguage', 'replaceAudio', 'keepOriginal'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('change', function() {
                if (!userSettings.audio_translation_settings) userSettings.audio_translation_settings = {};
                const key = id.replace(/([A-Z])/g, '_$1').toLowerCase();
                userSettings.audio_translation_settings[key] = element.type === 'checkbox' ? this.checked : this.value;
                saveUserSettings();
            });
        }
    });

    // Output file settings
    const outputFieldMap = {
        'saveVideo': 'save_video',
        'saveOriginalTranscript': 'save_original_transcript',
        'saveTranslatedTranscript': 'save_translated_transcript', 
        'saveOriginalSubtitles': 'save_original_subtitles',
        'saveTranslatedSubtitles': 'save_translated_subtitles',
        'saveTranslatedAudio': 'save_translated_audio'
    };
    
    Object.keys(outputFieldMap).forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('change', function() {
                if (!userSettings.file_output_settings) userSettings.file_output_settings = {};
                userSettings.file_output_settings[outputFieldMap[id]] = this.checked;
                console.log('Output settings updated:', userSettings.file_output_settings);
                saveUserSettings();
            });
        }
    });

    // Process button
    document.getElementById('startProcessing').addEventListener('click', showProcessConfirmation);
    document.getElementById('confirmProcess').addEventListener('click', startProcessing);
}

// Setup file uploads
function setupFileUploads() {
    // Video upload
    setupFileUpload('videoFile', 'videoUploadZone', handleVideoUpload);
    
    // Video URL download
    const downloadVideoBtn = document.getElementById('downloadVideoBtn');
    if (downloadVideoBtn) {
        downloadVideoBtn.addEventListener('click', handleVideoUrlDownload);
    }
    
    // Logo upload
    setupFileUpload('logoFile', 'logoUploadZone', handleLogoUpload);
    
    // CTA upload
    setupFileUpload('ctaFile', 'ctaUploadZone', handleCTAUpload);
    
    // Thumbnail images
    document.getElementById('thumbnailImages').addEventListener('change', handleThumbnailImages);
}

// Generic file upload setup
function setupFileUpload(inputId, zoneId, handler) {
    const input = document.getElementById(inputId);
    const zone = document.getElementById(zoneId);
    
    input.addEventListener('change', handler);
    
    zone.addEventListener('click', () => input.click());
    
    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });
    
    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });
    
    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        input.files = e.dataTransfer.files;
        handler.call(input);
    });
}

// Handle video upload
async function handleVideoUpload() {
    const file = this.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/upload/video', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            showVideoPreview(result);
        } else {
            showError('Failed to upload video');
        }
    } catch (error) {
        console.error('Error uploading video:', error);
        showError('Error uploading video');
    }
}

// Show video preview
function showVideoPreview(videoInfo) {
    const preview = document.getElementById('videoPreview');
    const video = document.getElementById('previewVideo');
    
    video.src = videoInfo.url;
    document.getElementById('videoDimensions').textContent = `${videoInfo.width}x${videoInfo.height}`;
    document.getElementById('videoDuration').textContent = formatDuration(videoInfo.duration);
    document.getElementById('videoFormat').textContent = videoInfo.format;
    
    preview.classList.remove('d-none');
}

// Handle logo upload
async function handleLogoUpload() {
    const file = this.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/upload/logo', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            showLogoPreview(result.url);
        } else {
            showError('Failed to upload logo');
        }
    } catch (error) {
        console.error('Error uploading logo:', error);
        showError('Error uploading logo');
    }
}

// Show logo preview
function showLogoPreview(url) {
    const preview = document.getElementById('logoPreview');
    const img = document.getElementById('logoImg');
    
    img.src = url;
    preview.classList.remove('d-none');
}

// Handle CTA upload
async function handleCTAUpload() {
    const file = this.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/upload/cta', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            showCTAPreview(result);
        } else {
            showError('Failed to upload CTA');
        }
    } catch (error) {
        console.error('Error uploading CTA:', error);
        showError('Error uploading CTA');
    }
}

// Show CTA preview
function showCTAPreview(ctaInfo) {
    const preview = document.getElementById('ctaPreview');
    const content = document.getElementById('ctaPreviewContent');
    
    if (ctaInfo.type === 'video') {
        content.innerHTML = `<video controls class="img-thumbnail" style="max-width: 200px;"><source src="${ctaInfo.url}" type="video/mp4"></video>`;
    } else {
        content.innerHTML = `<img src="${ctaInfo.url}" class="img-thumbnail" style="max-width: 200px;">`;
    }
    
    preview.classList.remove('d-none');
}

// Handle thumbnail images upload
function handleThumbnailImages() {
    // Implementation for custom thumbnail images
    updateThumbnailPreview();
}

// Update thumbnail preview
function updateThumbnailPreview() {
    const preview = document.getElementById('thumbnailPreview');
    const text = document.getElementById('thumbnailText').value;
    const fontSize = document.getElementById('thumbnailFontSize').value;
    const textColor = document.getElementById('thumbnailTextColor').value;
    
    if (text) {
        preview.innerHTML = `
            <div style="
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                color: ${textColor};
                font-size: ${fontSize}px;
                font-weight: bold;
                text-align: center;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
            ">${text}</div>
        `;
    } else {
        const previewText = getTranslation('common.preview_will_appear') || 'Preview will appear here';
        preview.innerHTML = `
            <div class="placeholder-content">
                <i class="fas fa-image fa-3x text-muted mb-2"></i>
                <p class="text-muted">${previewText}</p>
            </div>
        `;
    }
}

// YouTube connection functions
async function connectToYouTube() {
    try {
        const response = await fetch('/api/youtube/auth');
        if (response.ok) {
            const result = await response.json();
            window.location.href = result.auth_url;
        }
    } catch (error) {
        console.error('Error connecting to YouTube:', error);
        showError('Error connecting to YouTube');
    }
}

async function disconnectFromYouTube() {
    try {
        await fetch('/api/youtube/disconnect', { method: 'POST' });
        showYouTubeDisconnected();
        userSettings.youtube_settings.connected = false;
        saveUserSettings();
    } catch (error) {
        console.error('Error disconnecting from YouTube:', error);
        showError('Error disconnecting from YouTube');
    }
}

function showYouTubeConnected(channelName) {
    document.getElementById('notConnected').classList.add('d-none');
    document.getElementById('connected').classList.remove('d-none');
    document.getElementById('channelName').textContent = channelName;
}

function showYouTubeDisconnected() {
    document.getElementById('notConnected').classList.remove('d-none');
    document.getElementById('connected').classList.add('d-none');
}

// Processing functions
function showProcessConfirmation() {
    const selectedFeatures = [];
    const featureElements = document.querySelectorAll('.feature-toggle:checked');
    
    featureElements.forEach(element => {
        const feature = element.getAttribute('data-feature');
        const label = element.nextElementSibling.textContent;
        selectedFeatures.push(label);
    });
    
    if (selectedFeatures.length === 0) {
        showError('Please select at least one feature to process');
        return;
    }
    
    const featuresList = document.getElementById('selectedFeatures');
    featuresList.innerHTML = selectedFeatures.map(feature => 
        `<li class="list-group-item"><i class="fas fa-check text-success me-2"></i>${feature}</li>`
    ).join('');
    
    new bootstrap.Modal(document.getElementById('processingModal')).show();
}

async function startProcessing() {
    bootstrap.Modal.getInstance(document.getElementById('processingModal')).hide();
    
    // Check authentication first
    if (typeof checkAuthBeforeProcessing !== 'undefined') {
        const canProcess = await checkAuthBeforeProcessing();
        if (!canProcess) {
            return; // User needs to authenticate
        }
    }
    
    const progressModal = new bootstrap.Modal(document.getElementById('progressModal'));
    progressModal.show();
    
    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userSettings),
            credentials: 'include' // Include cookies for auth
        });
        
        if (response.ok) {
            const result = await response.json();
            
            // Show progress updates
            if (result.task_id) {
                monitorProgress(result.task_id);
            }
            
            // Show tier info if available
            if (result.tier) {
                console.log(`Processing started with ${result.tier} tier`);
            }
        } else {
            const errorData = await response.json();
            
            // Handle auth errors specially
            if (response.status === 401 && typeof authManager !== 'undefined') {
                progressModal.hide();
                new bootstrap.Modal(document.getElementById('authRequiredModal')).show();
                return;
            } else if (response.status === 402) {
                // Payment required
                progressModal.hide();
                if (errorData.detail && errorData.detail.action_required === 'upgrade') {
                    new bootstrap.Modal(document.getElementById('upgradeModal')).show();
                }
                showError(errorData.detail.message || 'Payment required');
                return;
            }
            
            throw new Error(errorData.detail || 'Processing failed');
        }
    } catch (error) {
        console.error('Error starting processing:', error);
        showError(typeof error === 'object' && error.message ? error.message : 'Error starting processing');
        progressModal.hide();
    }
}

// Monitor processing progress
async function monitorProgress(taskId) {
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    
    const checkProgress = async () => {
        try {
            const response = await fetch(`/api/progress/${taskId}`);
            if (response.ok) {
                const progress = await response.json();
                
                progressBar.style.width = `${progress.percentage}%`;
                progressText.textContent = progress.message;
                
                if (progress.status === 'completed') {
                    setTimeout(() => {
                        bootstrap.Modal.getInstance(document.getElementById('progressModal')).hide();
                        showSuccess('Processing completed successfully!');
                    }, 1000);
                } else if (progress.status === 'failed') {
                    bootstrap.Modal.getInstance(document.getElementById('progressModal')).hide();
                    showError('Processing failed: ' + progress.error);
                } else {
                    setTimeout(checkProgress, 2000);
                }
            }
        } catch (error) {
            console.error('Error checking progress:', error);
        }
    };
    
    checkProgress();
}

// Handle video URL download
async function handleVideoUrlDownload() {
    const videoUrl = document.getElementById('videoUrl').value.trim();
    
    if (!videoUrl) {
        showError(getTranslation('video_upload.url_required') || 'Please enter a video URL');
        return;
    }
    
    // Basic URL validation
    if (!isValidVideoUrl(videoUrl)) {
        showError(getTranslation('video_upload.invalid_url') || 'Please enter a valid video URL');
        return;
    }
    
    const downloadProgress = document.getElementById('downloadProgress');
    const downloadBtn = document.getElementById('downloadVideoBtn');
    
    try {
        // Show loading state
        downloadProgress.classList.remove('d-none');
        downloadBtn.disabled = true;
        downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i><span data-i18n="common.loading">Loading...</span>';
        
        // Make request to download video
        const response = await fetch('/api/download-video', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: videoUrl })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to download video');
        }
        
        const result = await response.json();
        
        // Clear the URL input
        document.getElementById('videoUrl').value = '';
        
        // Simulate file selection to trigger video preview
        await displayVideoPreview(result.filename, result.file_info);
        
        showSuccess(getTranslation('video_upload.download_success') || 'Video downloaded successfully!');
        
    } catch (error) {
        showError(error.message);
    } finally {
        // Reset UI state
        downloadProgress.classList.add('d-none');
        downloadBtn.disabled = false;
        downloadBtn.innerHTML = '<i class="fas fa-download me-2"></i><span data-i18n="video_upload.download">Download</span>';
    }
}

// Validate video URL
function isValidVideoUrl(url) {
    try {
        const urlObj = new URL(url);
        const validExtensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'];
        const pathname = urlObj.pathname.toLowerCase();
        
        // Check if URL has a video extension or is from known video platforms
        return validExtensions.some(ext => pathname.includes(ext)) || 
               url.includes('youtube.com') || 
               url.includes('youtu.be') ||
               url.includes('vimeo.com') ||
               url.includes('dailymotion.com');
    } catch {
        return false;
    }
}

// Display video preview from downloaded file
async function displayVideoPreview(filename, fileInfo) {
    const videoPreview = document.getElementById('videoPreview');
    const previewVideo = document.getElementById('previewVideo');
    const videoDimensions = document.getElementById('videoDimensions');
    const videoDuration = document.getElementById('videoDuration');
    const videoFormat = document.getElementById('videoFormat');
    
    // Set video source
    previewVideo.src = `/api/uploads/${filename}`;
    
    // Update video info
    videoDimensions.textContent = `${fileInfo.width}x${fileInfo.height}`;
    videoDuration.textContent = formatDuration(fileInfo.duration);
    videoFormat.textContent = fileInfo.format;
    
    // Show preview
    videoPreview.classList.remove('d-none');
}

// Utility functions
function formatDuration(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function showError(message) {
    // Simple alert for now - can be replaced with a toast notification
    alert(message);
}

function showSuccess(message) {
    // Simple alert for now - can be replaced with a toast notification
    alert(message);
}