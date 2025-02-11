from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                             QGridLayout, QLabel, QFrame, QPushButton,
                             QVBoxLayout, QHBoxLayout, QSlider, QScrollArea, QSizePolicy, QStyle)
from PySide6.QtCore import Qt, QUrl, Slot, Signal, QPropertyAnimation, QEasingCurve, Property, QPoint, QRect
from PySide6.QtGui import QPixmap, QIcon, QDragEnterEvent, QDropEvent
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from mutagen import File
from mutagen.id3 import ID3
import io

class TileWidget(QFrame):
    def __init__(self, title=""):
        super().__init__()
        self.setFrameStyle(QFrame.Box)
        self.setStyleSheet("""
            QFrame {
                background-color: #2D2D2D;
                border: 1px solid #3D3D3D;
                border-radius: 4px;
            }
        """)
        layout = QGridLayout(self)
        self.label = QLabel(title)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: white;")
        layout.addWidget(self.label)

class AlbumTile(TileWidget):
    clicked = Signal(str)  # 发送专辑路径信号
    
    def __init__(self, title="", cover_path=None, music_path=None, is_current_playing=False):
        super().__init__(title)
        self.music_path = music_path
        self.metadata = {}
        self.is_current_playing = is_current_playing
        self.setup_ui(cover_path)
        if music_path:
            self.load_metadata()
    
    def setup_ui(self, cover_path):
        if cover_path:
            pixmap = QPixmap(cover_path)
            scaled_pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.label.setPixmap(scaled_pixmap)
        self.setMinimumSize(200, 200)
        self.setAcceptDrops(True)  # 允许拖放
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        files = event.mimeData().urls()
        if files:
            file_path = files[0].toLocalFile()
            if file_path.lower().endswith(('.mp3', '.wav', '.flac')):
                self.music_path = file_path
                self.label.setText(file_path.split('/')[-1])
    
    def load_metadata(self):
        try:
            audio = File(self.music_path)
            if hasattr(audio, 'tags'):
                # MP3 文件处理
                if isinstance(audio.tags, ID3):
                    # 获取标题
                    if 'TIT2' in audio.tags:
                        self.metadata['title'] = str(audio.tags['TIT2'])
                    # 获取封面
                    if 'APIC:' in audio.tags:
                        img_data = audio.tags['APIC:'].data
                        pixmap = QPixmap()
                        pixmap.loadFromData(img_data)
                        scaled_pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.label.setPixmap(scaled_pixmap)
                        self.metadata['cover'] = img_data
                    
                    # 尝试不同的歌词标签格式
                    lyrics_tags = ['USLT::XXX', 'USLT::eng', 'USLT::', 'USLT', 
                                 'SYLT::XXX', 'SYLT::eng', 'SYLT::', 'SYLT']
                    
                    for tag in lyrics_tags:
                        if tag in audio.tags:
                            lyrics_frame = audio.tags[tag]
                            if hasattr(lyrics_frame, 'text'):
                                self.metadata['lyrics'] = lyrics_frame.text
                                break
                            elif hasattr(lyrics_frame, 'lyrics'):
                                self.metadata['lyrics'] = lyrics_frame.lyrics
                                break
                    
                    # 直接遍历所有标签寻找歌词
                    if 'lyrics' not in self.metadata:
                        for key in audio.tags.keys():
                            if 'USLT' in key or 'SYLT' in key:
                                print(f"Found lyrics tag: {key}")
                                print(f"Content: {audio.tags[key]}")
                                if hasattr(audio.tags[key], 'text'):
                                    self.metadata['lyrics'] = audio.tags[key].text
                                    break
            
            # 如果没有找到标题，使用文件名
            if 'title' not in self.metadata:
                self.metadata['title'] = self.music_path.split('/')[-1]
                self.label.setText(self.metadata['title'])
                
        except Exception as e:
            print(f"Error loading metadata: {e}")
            self.label.setText(self.music_path.split('/')[-1])

class CurrentAlbumTile(AlbumTile):
    def __init__(self, title=""):
        super().__init__(title, is_current_playing=True)
        self.progress = None
        self.setup_progress()
    
    def setup_progress(self):
        layout = self.layout()
        self.progress = QSlider(Qt.Horizontal)
        self.progress.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #3D3D3D;
            }
            QSlider::handle:horizontal {
                background: white;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
        """)
        self._slider_pressed = False
        self.progress.sliderPressed.connect(self.on_slider_pressed)
        self.progress.sliderReleased.connect(self.on_slider_released)
        layout.addWidget(self.progress)
        
    def on_slider_pressed(self):
        self._slider_pressed = True
        
    def on_slider_released(self):
        self._slider_pressed = False

class LyricsTile(TileWidget):
    def __init__(self):
        super().__init__("Lyrics")
        self.lyrics_lines = []  # [(time_in_ms, lyric_text), ...]
        self.current_line = 0
        self.setup_ui()
    
    def setup_ui(self):
        self.setLayout(QVBoxLayout())
        
        # 创建可滚动的歌词显示区域
        self.lyrics_widget = QWidget()
        self.lyrics_layout = QVBoxLayout(self.lyrics_widget)
        self.lyrics_labels = []
        
        # 创建滚动区域
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.lyrics_widget)
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("""
            QScrollArea { 
                background: transparent; 
                border: none;
            }
            QWidget { 
                background: transparent; 
            }
        """)
        
        self.layout().addWidget(self.scroll)
        
        # 添加点击事件处理
        self.lyrics_widget.mousePressEvent = self.on_lyrics_click
    
    def on_lyrics_click(self, event):
        # 获取点击位置对应的歌词标签
        pos = event.position()  # 使用 position() 替代 pos()
        for i, label in enumerate(self.lyrics_labels):
            label_pos = label.mapTo(self.lyrics_widget, QPoint(0, 0))
            label_rect = QRect(label_pos, label.size())
            if label_rect.contains(pos.toPoint()):  # 转换为 QPoint
                if i < len(self.lyrics_lines):
                    # 发送时间位置给播放器
                    time_ms = self.lyrics_lines[i][0]
                    if hasattr(self, 'player'):
                        self.player.setPosition(time_ms)
                break
    
    def parse_lrc_time(self, time_str):
        # 解析 [mm:ss.xx] 格式
        try:
            minutes, seconds = time_str[1:-1].split(':')
            total_seconds = float(minutes) * 60 + float(seconds)
            return int(total_seconds * 1000)  # 转换为毫秒
        except:
            return 0
    
    def parse_lrc(self, lrc_text):
        self.lyrics_lines = []
        if not lrc_text:
            return
        
        for line in lrc_text.split('\n'):
            line = line.strip()
            if not line or not line.startswith('['):
                continue
            
            # 处理一行可能有多个时间标签的情况
            time_tags = []
            text = line
            while text.startswith('['):
                time_end = text.find(']')
                if time_end == -1:
                    break
                time_str = text[:time_end + 1]
                time_ms = self.parse_lrc_time(time_str)
                if time_ms > 0:
                    time_tags.append(time_ms)
                text = text[time_end + 1:].strip()
            
            # 为每个时间标签添加歌词
            for time_ms in time_tags:
                if text:
                    self.lyrics_lines.append((time_ms, text))
        
        # 按时间排序
        self.lyrics_lines.sort(key=lambda x: x[0])
        self.update_lyrics_display()
    
    def update_lyrics_display(self):
        # 清除现有歌词
        for label in self.lyrics_labels:
            self.lyrics_layout.removeWidget(label)
            label.deleteLater()
        self.lyrics_labels.clear()
        
        # 创建新的歌词标签
        for _, text in self.lyrics_lines:
            label = QLabel(text)
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("""
                color: #808080;
                font-size: 14px;
                padding: 5px;
            """)
            self.lyrics_labels.append(label)
            self.lyrics_layout.addWidget(label)
        
        if not self.lyrics_lines:
            label = QLabel("暂无歌词")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #808080; font-size: 14px;")
            self.lyrics_labels.append(label)
            self.lyrics_layout.addWidget(label)
    
    def update_position(self, position):
        if not self.lyrics_lines:
            return
        
        # 查找当前应该高亮的歌词
        current_line = -1
        for i, (time, _) in enumerate(self.lyrics_lines):
            if time > position:
                break
            current_line = i
        
        if current_line != self.current_line:
            # 更新高亮
            for i, label in enumerate(self.lyrics_labels):
                if i == current_line:
                    label.setStyleSheet("""
                        color: white;
                        font-size: 16px;
                        font-weight: bold;
                        padding: 5px;
                    """)
                else:
                    label.setStyleSheet("""
                        color: #808080;
                        font-size: 14px;
                        padding: 5px;
                    """)
            
            # 滚动到当前行
            if current_line >= 0:
                label = self.lyrics_labels[current_line]
                # 计算滚动位置，使当前行居中
                scroll_pos = label.pos().y() - (self.scroll.height() // 2) + (label.height() // 2)
                self.scroll.verticalScrollBar().setValue(max(0, scroll_pos))
            
            self.current_line = current_line
    
    def update_lyrics(self, text):
        self.current_line = -1
        self.parse_lrc(text)

class ControlsTile(TileWidget):
    def __init__(self, audio_player):
        super().__init__("Controls")
        self.audio_player = audio_player
        # 完全删除原有布局
        QWidget().setLayout(self.layout())
        self.setup_controls()
    
    def setup_controls(self):
        main_layout = QVBoxLayout(self)
        
        # 播放控制按钮
        buttons_layout = QHBoxLayout()
        prev_btn = QPushButton("⏮")
        play_btn = QPushButton("⏯")
        next_btn = QPushButton("⏭")
        
        for btn in [prev_btn, play_btn, next_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    color: white;
                    background: #3D3D3D;
                    border: none;
                    padding: 10px;
                    border-radius: 20px;
                    min-width: 40px;
                }
                QPushButton:hover {
                    background: #4D4D4D;
                }
            """)
            buttons_layout.addWidget(btn)
        
        # 音量控制
        volume_layout = QHBoxLayout()
        volume_label = QLabel("🔊")
        volume_label.setStyleSheet("color: white;")
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setMaximumWidth(100)
        self.volume.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #3D3D3D;
            }
            QSlider::handle:horizontal {
                background: white;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
        """)
        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.volume)
        
        main_layout.addLayout(buttons_layout)
        main_layout.addLayout(volume_layout)
        
        # 添加按钮回调
        prev_btn.clicked.connect(self.audio_player.prev_song)
        play_btn.clicked.connect(self.audio_player.play)
        next_btn.clicked.connect(self.audio_player.next_song)
        
        # 音量控制回调
        self.volume.valueChanged.connect(self.audio_player.audio_output.setVolume)

class AudioPlayer:
    def __init__(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        # 当前播放列表
        self.playlist = []
        self.current_index = -1
    
    def add_song(self, path):
        self.playlist.append(path)
    
    def play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()
    
    def next_song(self):
        if not self.playlist:
            return
        self.current_index = (self.current_index + 1) % len(self.playlist)
        self.load_current_song()
    
    def prev_song(self):
        if not self.playlist:
            return
        self.current_index = (self.current_index - 1) % len(self.playlist)
        self.load_current_song()
    
    def load_current_song(self):
        if 0 <= self.current_index < len(self.playlist):
            self.player.setSource(QUrl.fromLocalFile(self.playlist[self.current_index]))
            self.player.play()

class ScrollableAlbumArea(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.layout = QGridLayout(self.container)  # 改用 QGridLayout
        self.layout.setSpacing(10)
        self.setWidget(self.container)
        
        # 当前显示的起始索引
        self.current_index = 0
        self.tiles = []
        
        # 动画设置
        self._scroll_pos = 0
        self.animation = QPropertyAnimation(self, b"scrollPosition")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # 添加控制按钮
        self.setup_controls()
    
    def setup_controls(self):
        # 左右翻页按钮
        self.prev_btn = QPushButton("◀")
        self.next_btn = QPushButton("▶")
        self.play_btn = QPushButton("▼")
        
        button_style = """
            QPushButton {
                color: white;
                background: rgba(61, 61, 61, 0.7);
                border: none;
                border-radius: 15px;
                padding: 5px;
                min-width: 30px;
                min-height: 30px;
            }
            QPushButton:hover {
                background: rgba(77, 77, 77, 0.8);
            }
        """
        
        for btn in [self.prev_btn, self.next_btn, self.play_btn]:
            btn.setStyleSheet(button_style)
        
        # 放置按钮
        self.prev_btn.setParent(self)
        self.next_btn.setParent(self)
        self.play_btn.setParent(self)
        
        # 连接信号
        self.prev_btn.clicked.connect(self.scroll_left)
        self.next_btn.clicked.connect(self.scroll_right)
        self.play_btn.clicked.connect(self.play_current)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 更新按钮位置
        h = self.height()
        w = self.width()
        
        # 左右按钮垂直居中
        self.prev_btn.move(10, h//2 - 15)
        self.next_btn.move(w - 40, h//2 - 15)
        
        # 播放按钮位于中间卡片上方
        center_x = w//2
        self.play_btn.move(center_x - 15, 10)
    
    def scroll_left(self):
        if len(self.tiles) <= 3:
            return
        self.current_index = (self.current_index - 1) % len(self.tiles)
        self.update_visible_tiles()
    
    def scroll_right(self):
        if len(self.tiles) <= 3:
            return
        self.current_index = (self.current_index + 1) % len(self.tiles)
        self.update_visible_tiles()
    
    def play_current(self):
        if len(self.tiles) <= 3:
            return
        # 获取中间卡片的索引
        center_idx = (self.current_index + 1) % len(self.tiles)
        center_tile = self.tiles[center_idx]
        if center_tile.music_path:
            center_tile.clicked.emit(center_tile.music_path)
    
    def add_tile(self, tile):
        self.tiles.append(tile)
        self.update_visible_tiles()
    
    def update_visible_tiles(self):
        # 清空现有布局
        for i in reversed(range(self.layout.count())): 
            self.layout.itemAt(i).widget().setParent(None)
        
        # 显示当前三张卡片
        for i in range(3):
            idx = (self.current_index + i) % len(self.tiles)
            if idx < len(self.tiles):
                self.layout.addWidget(self.tiles[idx], 0, i)

class TilesPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tiles Music Player")
        self.setMinimumSize(800, 600)
        self.audio_player = AudioPlayer()
        self.setup_ui()
        self.load_music_library()
    
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QGridLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 替换上排固定专辑为可滚动区域
        self.scroll_area = ScrollableAlbumArea()
        layout.addWidget(self.scroll_area, 0, 0, 1, 3)
        
        # 下排：功能区
        self.lyrics = LyricsTile()
        self.current_album = CurrentAlbumTile("当前播放")
        self.controls = ControlsTile(self.audio_player)
        
        # 设置固定大小策略
        for widget in [self.lyrics, self.current_album, self.controls]:
            widget.setMinimumSize(200, 200)
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        layout.addWidget(self.lyrics, 1, 0)
        layout.addWidget(self.current_album, 1, 1)
        layout.addWidget(self.controls, 1, 2)
        
        # 连接音乐播放状态变化
        self.audio_player.player.sourceChanged.connect(self.on_source_changed)
        self.audio_player.player.mediaStatusChanged.connect(self.on_status_changed)
        
        # 将进度条连接移到这里
        self.current_album.progress.sliderMoved.connect(self.audio_player.player.setPosition)
        self.audio_player.player.positionChanged.connect(self.current_album.progress.setValue)
        self.audio_player.player.durationChanged.connect(self.current_album.progress.setMaximum)
        
        # 连接播放器到歌词组件
        self.lyrics.player = self.audio_player.player
        self.audio_player.player.positionChanged.connect(self.lyrics.update_position)
    
    def load_music_library(self):
        import os
        music_dir = "data"
        if not os.path.exists(music_dir):
            os.makedirs(music_dir)
            
        supported_formats = ('.mp3', '.wav', '.flac')
        for file in os.listdir(music_dir):
            if file.lower().endswith(supported_formats):
                music_path = os.path.join(music_dir, file)
                cover_path = None
                
                # 不将当前播放的音乐添加到上排
                if music_path != self.current_album.music_path:
                    tile = AlbumTile(file, cover_path, music_path)
                    tile.clicked.connect(self.play_album)
                    self.scroll_area.add_tile(tile)
        
        # 添加空白拖放区域
        empty_tile = AlbumTile("拖放音乐到这里")
        self.scroll_area.add_tile(empty_tile)
    
    def play_album(self, music_path):
        # 查找对应的 tile
        for tile in self.scroll_area.tiles:
            if tile.music_path == music_path:
                # 更新当前播放专辑
                self.current_album.music_path = music_path
                self.current_album.label.setText(tile.metadata.get('title', music_path.split('/')[-1]))
                
                # 更新封面
                if 'cover' in tile.metadata:
                    pixmap = QPixmap()
                    pixmap.loadFromData(tile.metadata['cover'])
                    scaled_pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.current_album.label.setPixmap(scaled_pixmap)
                
                # 更新歌词
                if 'lyrics' in tile.metadata:
                    self.lyrics.update_lyrics(tile.metadata['lyrics'])
                else:
                    self.lyrics.update_lyrics("暂无歌词")
                break
        
        # 播放音乐
        self.audio_player.playlist = [music_path]
        self.audio_player.current_index = 0
        self.audio_player.load_current_song()
    
    @Slot()
    def on_source_changed(self):
        pass
    
    @Slot(QMediaPlayer.MediaStatus)
    def on_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            # 音乐加载完成，可以更新界面
            pass
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            # 播放结束，可以自动播放下一首
            self.audio_player.next_song()

if __name__ == "__main__":
    app = QApplication([])
    window = TilesPlayer()
    window.show()
    app.exec() 