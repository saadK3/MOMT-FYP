The given H format is from world (X, Y) to pixel (u, v)

The pixel values are not normalized and span the frame's height and width. 
The given videos have (1280, 960) and (1920, 1080) resolutions.

The world unit is not meters though, it looks like `10e-05` of homography's world unit corresponds to 1 meter in actual. 
In the code I have taken this assumption and things that represent world units e.g. "det_birdeye" are actually homography 
world unit divided by `10e-5`

For each video along with JSON, we have a video showing the results annotated corresponding to JSON. Each video has fps of 10.

Each video has a corresponding image with homographic plane in pixel space "*_H_plane.jpg". These are generated with (1280, 960) 
resolution being fixed so it will be correct for the (1280, 960) resolution videos, for others higher resolutions it would only represent the top-left 
(1280, 960) pixels and won't represent complete viewport.  Also the H plane is drawn between world points corresponding to fixed pixel points. So its utility would vary.
Though the track jsons are agnostic to resolution so they are correct for any resolution.

resolutions for reference:

S04_c019.mp4: 2560x1920
S05_c034.mp4: 1920x1080
S06_c046.mp4: 1280x720
S05_c026.mp4: 1920x1080
S06_c044.mp4: 1280x960
S05_c028.mp4: 1920x1080
S01_c005.mp4: 1280x960
S06_c041.mp4: 1280x960
S05_c020.mp4: 2560x1920
S05_c022.mp4: 1920x1080
S03_c015.mp4: 1920x1080
S04_c026.mp4: 1920x1080
S04_c022.mp4: 1920x1080
S02_c007.mp4: 1920x1080
S04_c032.mp4: 1600x1200
S05_c027.mp4: 1920x1080
S05_c029.mp4: 1920x1080
S04_c021.mp4: 1920x1080
S06_c043.mp4: 1280x960
S03_c011.mp4: 2560x1920
S02_c008.mp4: 1920x1080
S05_c035.mp4: 1920x1080
S04_c038.mp4: 2560x1920
S05_c023.mp4: 2560x1920
S04_c030.mp4: 1600x1200
S05_c016.mp4: 1920x1080
S04_c017.mp4: 1920x1080
S05_c036.mp4: 1920x1080
S01_c002.mp4: 1920x1080
S04_c023.mp4: 2560x1920
S04_c027.mp4: 1920x1080
S04_c020.mp4: 2560x1920
S04_c033.mp4: 1920x1080
S05_c018.mp4: 2560x1920
S04_c031.mp4: 1600x1200
S04_c018.mp4: 2560x1920
S03_c014.mp4: 1920x1080
S06_c042.mp4: 1280x960
S02_c006.mp4: 1920x1080
S01_c003.mp4: 1920x1080
S05_c024.mp4: 2560x1920
S03_c010.mp4: 1920x1080
S04_c028.mp4: 1920x1080
S01_c004.mp4: 1920x1080
S04_c016.mp4: 1920x1080
S05_c025.mp4: 2560x1920
S05_c017.mp4: 1920x1080
S04_c036.mp4: 1920x1080
S03_c012.mp4: 2560x1920
S01_c001.mp4: 1920x1080
S05_c021.mp4: 1920x1080
S05_c019.mp4: 2560x1920
S04_c024.mp4: 2560x1920
S04_c039.mp4: 2560x1920
S02_c009.mp4: 1920x1080
S06_c045.mp4: 1280x720
S04_c034.mp4: 1920x1080
S05_c033.mp4: 1920x1080
S03_c013.mp4: 2560x1920
S05_c010.mp4: 1920x1080
S04_c040.mp4: 1600x1200
S04_c029.mp4: 1920x1080
S04_c025.mp4: 2560x1920
S04_c037.mp4: 1920x1088
S04_c035.mp4: 1920x1080