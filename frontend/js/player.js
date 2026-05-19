/**
 * 播放器模块 - 音频播放、进度保存、断点续播
 */
let audio = null;
let currentCourse = null;
let currentAudioIndex = 0;
let progressSaveTimer = null;
let sessionStartTime = 0;
let lastPosition = 0;
let isPlaying = false;

// 页面加载时解析课程ID
const urlParams = new URLSearchParams(window.location.search);
const courseId = urlParams.get('course');

document.addEventListener('DOMContentLoaded', () => {
    if (!courseId) {
        document.body.innerHTML = '<div class="text-center py-20 text-red-500">未指定课程ID</div>';
        return;
    }
    initAuth();
    loadCourseAndSetupPlayer();
});

async function loadCourseAndSetupPlayer() {
    try {
        const data = await CourseAPI.getDetail(courseId);
        currentCourse = data.course;

        renderCourseInfo(currentCourse);
        renderPlaylist(currentCourse.audio_files);
        setupAudioPlayer();

        // 解析 URL 参数：audio 指定音频索引，t 指定播放时间
        const urlParams = new URLSearchParams(window.location.search);
        const targetAudioId = parseInt(urlParams.get('audio'), 10);
        const targetTime = parseFloat(urlParams.get('t'));

        if (currentCourse.audio_files && currentCourse.audio_files.length > 0) {
            let startIndex = 0;

            // 如果 URL 指定了 audio_id，找到对应索引
            if (!isNaN(targetAudioId)) {
                const foundIndex = currentCourse.audio_files.findIndex(a => a.id === targetAudioId);
                if (foundIndex >= 0) {
                    startIndex = foundIndex;
                }
            } else {
                // 查找上次播放的音频（有进度的）
                for (let i = 0; i < currentCourse.audio_files.length; i++) {
                    if (currentCourse.audio_files[i].current_time > 0 && !currentCourse.audio_files[i].completed) {
                        startIndex = i;
                        break;
                    }
                }
            }

            loadAudio(startIndex, !isNaN(targetTime) ? targetTime : null);
        }
    } catch (err) {
        document.getElementById('course-title').textContent = '加载失败';
        console.error(err);
    }
}

function renderCourseInfo(course) {
    document.getElementById('course-title').textContent = course.title;
    document.getElementById('course-desc').textContent = course.description || '';
    document.getElementById('course-category').textContent = course.category;
}

function renderPlaylist(audioFiles) {
    const list = document.getElementById('playlist');
    if (!audioFiles || audioFiles.length === 0) {
        list.innerHTML = '<div class="text-gray-400 text-center py-10">暂无音频</div>';
        return;
    }

    list.innerHTML = audioFiles.map((audio, i) => `
        <div class="flex items-center p-3 rounded-lg cursor-pointer hover:bg-gray-100 transition ${i === currentAudioIndex ? 'bg-blue-50 border-l-4 border-blue-500' : ''}"
             id="playlist-item-${i}"
             onclick="loadAudio(${i})">
            <div class="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-sm text-gray-600 mr-3">
                ${audio.completed ? '✓' : (i + 1)}
            </div>
            <div class="flex-1 min-w-0">
                <div class="text-sm font-medium truncate ${i === currentAudioIndex ? 'text-blue-700' : 'text-gray-800'}">${audio.title}</div>
                <div class="text-xs text-gray-400">${formatDuration(audio.duration)}</div>
            </div>
            ${audio.current_time > 0 && !audio.completed ? `
                <div class="text-xs text-green-600 ml-2">${(audio.current_time/audio.duration*100).toFixed(0)}%</div>
            ` : ''}
        </div>
    `).join('');
}

function setupAudioPlayer() {
    audio = document.getElementById('main-audio');
    if (!audio) return;

    // 应用全局保存的倍速
    const savedSpeed = getSavedSpeed();
    audio.playbackRate = savedSpeed;
    updateSpeedButtonStyles(savedSpeed);

    // 监听播放进度
    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('play', onPlay);
    audio.addEventListener('pause', onPause);
    audio.addEventListener('ended', onEnded);
    audio.addEventListener('seeked', onSeeked);

    // 进度条拖拽
    const progressBar = document.getElementById('progress-bar');
    if (progressBar) {
        progressBar.addEventListener('click', (e) => {
            const rect = progressBar.getBoundingClientRect();
            const percent = (e.clientX - rect.left) / rect.width;
            if (audio.duration) {
                audio.currentTime = percent * audio.duration;
            }
        });
    }
}

// 倍速切换（全局设置，保存到 localStorage）
function setSpeed(speed) {
    if (!audio) return;
    audio.playbackRate = speed;
    localStorage.setItem('playback_speed', speed);
    updateSpeedButtonStyles(speed);
}

function updateSpeedButtonStyles(speed) {
    document.querySelectorAll('.speed-btn').forEach(btn => {
        const btnSpeed = parseFloat(btn.dataset.speed);
        if (btnSpeed === speed) {
            btn.className = 'speed-btn px-4 py-2 rounded-full text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition shadow-sm';
        } else {
            btn.className = 'speed-btn px-4 py-2 rounded-full text-sm font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 transition';
        }
    });
}

function getSavedSpeed() {
    const saved = localStorage.getItem('playback_speed');
    if (saved) {
        const speed = parseFloat(saved);
        if (!isNaN(speed) && speed > 0) {
            return speed;
        }
    }
    return 1.0;
}

let preloadAudio = null;  // 预加载音频元素

async function loadAudio(index, forceTime = null) {
    if (!currentCourse || !currentCourse.audio_files || index < 0 || index >= currentCourse.audio_files.length) return;

    currentAudioIndex = index;
    const audioFile = currentCourse.audio_files[index];

    // 更新音频源
    const src = `/api/audio/${audioFile.id}/stream`;
    if (audio.src !== src) {
        audio.src = src;
        audio.load();
    }

    // 更新UI高亮
    document.querySelectorAll('[id^="playlist-item-"]').forEach((el, i) => {
        el.className = el.className.replace(/bg-blue-50|border-l-4|border-blue-500/g, '');
        if (i === index) {
            el.classList.add('bg-blue-50', 'border-l-4', 'border-blue-500');
        }
    });

    // 更新当前播放信息
    document.getElementById('current-title').textContent = audioFile.title;
    document.getElementById('current-index').textContent = `${index + 1} / ${currentCourse.audio_files.length}`;

    // 检查收藏状态
    checkFavoriteStatus(audioFile.id);

    // 恢复上次播放位置（断点续播）
    if (forceTime !== null && forceTime >= 0) {
        audio.currentTime = forceTime;
    } else if (audioFile.current_time > 0 && !audioFile.completed) {
        audio.currentTime = audioFile.current_time;
    } else {
        audio.currentTime = 0;
    }

    lastPosition = audio.currentTime;
    sessionStartTime = Date.now();

    // 应用全局倍速
    const savedSpeed = getSavedSpeed();
    audio.playbackRate = savedSpeed;

    // 自动播放
    audio.play().catch(e => console.log('自动播放被阻止:', e));

    // 预加载下一首音频
    preloadNextAudio();

    // 更新浏览器地址栏，确保分享时 URL 包含当前音频
    updateBrowserUrl(audioFile.id);
}

function updateBrowserUrl(audioId) {
    const params = new URLSearchParams(window.location.search);
    params.set('audio', audioId);
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    history.replaceState({ audioId }, '', newUrl);
}

function preloadNextAudio() {
    if (!currentCourse || !currentCourse.audio_files) return;
    const nextIndex = currentAudioIndex + 1;
    if (nextIndex >= currentCourse.audio_files.length) return;

    const nextAudioFile = currentCourse.audio_files[nextIndex];
    const src = `/api/audio/${nextAudioFile.id}/stream`;

    // 复用或创建预加载音频元素
    if (!preloadAudio) {
        preloadAudio = document.createElement('audio');
        preloadAudio.preload = 'auto';
        preloadAudio.volume = 0;
        preloadAudio.style.display = 'none';
        document.body.appendChild(preloadAudio);
    }

    // 如果已经在预加载同一首，不做重复操作
    if (preloadAudio.src !== window.location.origin + src) {
        preloadAudio.src = src;
        preloadAudio.load();
    }
}

// 收藏功能
let currentAudioIdForFav = null;

async function checkFavoriteStatus(audioId) {
    currentAudioIdForFav = audioId;
    try {
        const data = await FavoriteAPI.check(audioId);
        updateFavoriteButton(data.favorited);
    } catch (e) {
        console.log('收藏状态检查失败:', e);
    }
}

function updateFavoriteButton(favorited) {
    const emptyIcon = document.getElementById('fav-icon-empty');
    const filledIcon = document.getElementById('fav-icon-filled');
    const btn = document.getElementById('fav-btn');
    const text = document.getElementById('fav-text');
    if (!emptyIcon || !filledIcon) return;

    if (favorited) {
        emptyIcon.classList.add('hidden');
        filledIcon.classList.remove('hidden');
        btn.classList.add('text-red-500', 'border-red-300', 'bg-red-50');
        btn.classList.remove('text-gray-500', 'border-gray-200');
        if (text) text.textContent = '已收藏';
    } else {
        emptyIcon.classList.remove('hidden');
        filledIcon.classList.add('hidden');
        btn.classList.remove('text-red-500', 'border-red-300', 'bg-red-50');
        btn.classList.add('text-gray-500', 'border-gray-200');
        if (text) text.textContent = '收藏';
    }
}

async function toggleFavorite() {
    if (!currentAudioIdForFav) return;
    try {
        const data = await FavoriteAPI.toggle(currentAudioIdForFav);
        updateFavoriteButton(data.favorited);
        // 显示提示
        showToast(data.message);
    } catch (e) {
        console.error('收藏操作失败:', e);
        showToast('操作失败，请登录后重试');
    }
}

function showToast(message) {
    const existing = document.getElementById('toast-msg');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'toast-msg';
    toast.className = 'fixed top-20 left-1/2 transform -translate-x-1/2 bg-gray-800 text-white px-4 py-2 rounded-lg shadow-lg z-50 text-sm animate-fade-in';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

function onTimeUpdate() {
    if (!audio) return;
    const current = audio.currentTime;
    const total = audio.duration || 0;

    // 更新进度条
    const progressBar = document.getElementById('progress-fill');
    if (progressBar && total > 0) {
        progressBar.style.width = `${(current / total * 100).toFixed(1)}%`;
    }

    // 更新时间显示
    document.getElementById('time-current').textContent = formatDuration(current);
    document.getElementById('time-total').textContent = formatDuration(total);

    // 每30秒保存一次进度（防频繁请求）
    if (Math.floor(current) % 30 === 0 && current > 0) {
        throttledSaveProgress(current);
    }
}

let throttleTimer = null;
function throttledSaveProgress(current) {
    if (throttleTimer) return;
    throttleTimer = setTimeout(() => {
        saveProgress(current);
        throttleTimer = null;
    }, 1000);
}

async function saveProgress(currentTime, completed = false) {
    if (!currentCourse) return;
    const audioFile = currentCourse.audio_files[currentAudioIndex];
    if (!audioFile) return;

    try {
        await PlayerAPI.saveProgress(audioFile.id, currentTime, completed);
    } catch (e) {
        console.warn('进度保存失败:', e.message);
    }
}

function onPlay() {
    isPlaying = true;
    sessionStartTime = Date.now();
    lastPosition = audio.currentTime;
    updatePlayButton(true);

    const audioFile = currentCourse.audio_files[currentAudioIndex];
    PlayerAPI.logAction(audioFile.id, 'play', audio.currentTime).catch(() => {});
}

function onPause() {
    isPlaying = false;
    updatePlayButton(false);

    // 计算本次实际收听时长
    const durationListened = (Date.now() - sessionStartTime) / 1000;
    const audioFile = currentCourse.audio_files[currentAudioIndex];

    // 保存进度
    saveProgress(audio.currentTime);

    // 记录日志
    if (durationListened > 1) {
        PlayerAPI.logAction(audioFile.id, 'pause', audio.currentTime, durationListened).catch(() => {});
    }
}

function onEnded() {
    isPlaying = false;
    updatePlayButton(false);

    const audioFile = currentCourse.audio_files[currentAudioIndex];
    PlayerAPI.logAction(audioFile.id, 'complete', audio.duration, audio.duration).catch(() => {});

    // 标记完成
    saveProgress(audio.duration, true);

    // 自动播放下一首
    if (currentAudioIndex < currentCourse.audio_files.length - 1) {
        loadAudio(currentAudioIndex + 1);
    }
}

function onSeeked() {
    const audioFile = currentCourse.audio_files[currentAudioIndex];
    PlayerAPI.logAction(audioFile.id, 'seek', audio.currentTime, 0).catch(() => {});
}

function updatePlayButton(playing) {
    const playIcon = document.getElementById('play-icon');
    const pauseIcon = document.getElementById('pause-icon');
    if (playIcon) playIcon.classList.toggle('hidden', playing);
    if (pauseIcon) pauseIcon.classList.toggle('hidden', !playing);
}

function togglePlay() {
    if (!audio) return;
    if (audio.paused) {
        audio.play();
    } else {
        audio.pause();
    }
}

function playNext() {
    if (currentAudioIndex < currentCourse.audio_files.length - 1) {
        loadAudio(currentAudioIndex + 1);
    }
}

function playPrev() {
    if (currentAudioIndex > 0) {
        loadAudio(currentAudioIndex - 1);
    }
}

// 分享弹窗
let shareQrCode = null;

function openShareModal() {
    const modal = document.getElementById('share-modal');
    if (!modal) return;

    const shareUrl = window.location.href;
    document.getElementById('share-link').value = shareUrl;

    // 生成二维码
    const qrContainer = document.getElementById('share-qrcode');
    qrContainer.innerHTML = '';
    shareQrCode = new QRCode(qrContainer, {
        text: shareUrl,
        width: 180,
        height: 180,
        colorDark: '#1f2937',
        colorLight: '#ffffff',
        correctLevel: QRCode.CorrectLevel.M
    });

    document.getElementById('copy-tip').textContent = '';
    modal.classList.remove('hidden');
}

function closeShareModal() {
    const modal = document.getElementById('share-modal');
    if (modal) modal.classList.add('hidden');
}

async function copyShareLink() {
    const input = document.getElementById('share-link');
    const tip = document.getElementById('copy-tip');
    if (!input) return;

    try {
        await navigator.clipboard.writeText(input.value);
        tip.textContent = '链接已复制，去微信粘贴给好友吧！';
    } catch (e) {
        // 降级方案
        input.select();
        input.setSelectionRange(0, 99999);
        const ok = document.execCommand('copy');
        tip.textContent = ok ? '链接已复制，去微信粘贴给好友吧！' : '复制失败，请手动复制链接';
    }

    setTimeout(() => { tip.textContent = ''; }, 3000);
}

// 页面卸载时保存进度
window.addEventListener('beforeunload', () => {
    if (audio && currentCourse) {
        const currentTime = audio.currentTime;
        const audioFile = currentCourse.audio_files[currentAudioIndex];
        if (audioFile) {
            // 使用 sendBeacon 确保数据发送
            const url = `${window.location.origin}/api/progress/${audioFile.id}`;
            const data = JSON.stringify({ current_time: currentTime, completed: false });
            navigator.sendBeacon(url, new Blob([data], { type: 'application/json' }));
        }
    }
});