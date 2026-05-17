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

        // 自动播放第一首，或继续上次的音频
        if (currentCourse.audio_files && currentCourse.audio_files.length > 0) {
            // 查找上次播放的音频（有进度的）
            let startIndex = 0;
            for (let i = 0; i < currentCourse.audio_files.length; i++) {
                if (currentCourse.audio_files[i].current_time > 0 && !currentCourse.audio_files[i].completed) {
                    startIndex = i;
                    break;
                }
            }
            loadAudio(startIndex);
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

    // 监听播放进度
    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('play', onPlay);
    audio.addEventListener('pause', onPause);
    audio.addEventListener('ended', onEnded);
    audio.addEventListener('seeked', onSeeked);

    // 设置倍速选择
    const speedSelect = document.getElementById('speed-select');
    if (speedSelect) {
        speedSelect.addEventListener('change', (e) => {
            audio.playbackRate = parseFloat(e.target.value);
        });
    }

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

function loadAudio(index) {
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

    // 恢复上次播放位置（断点续播）
    if (audioFile.current_time > 0 && !audioFile.completed) {
        audio.currentTime = audioFile.current_time;
    } else {
        audio.currentTime = 0;
    }

    lastPosition = audio.currentTime;
    sessionStartTime = Date.now();

    // 自动播放
    audio.play().catch(e => console.log('自动播放被阻止:', e));
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
    const btn = document.getElementById('play-btn');
    if (!btn) return;
    btn.innerHTML = playing
        ? '<svg class="w-8 h-8" fill="currentColor" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>'
        : '<svg class="w-8 h-8" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
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