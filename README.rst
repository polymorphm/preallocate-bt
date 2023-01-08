README
======

`preallocate-bt` is tiny utility for making possible to download torrents
directly to slow USB-flash-drives. It correctly (slowly) preallocates files
which will be downloaded by Transmission Bittorrent Client (or other compatibility
software).

How To Use
----------

1. Prepare (preallocate) files by invoke the utility. For example::

    ./preallocate-bt -v -- \
            ~/Downloads/'Game of Thrones ALL SEASONS with nice quality.torrent' \
            /path/to/slow/slow/usb/drive/with/my/favorite/films/directory

2. Open Transmission Bittorrent Client for this `.torrent`-file and start
   downloading into that prepared (preallocated) destination.

That's all!

But What The Problem Was Solved At All?
---------------------------------------

The first thing is `exfat` filesystem can't do with holes in files. If
an application software tries to make a huge hole it becomes to a huge solid
write operation (a zero filling procedure).

The second thing is USB-flash-drives could work very badly during active writes
(in Linux), especially if it happens not very accurately by an application
software.

So it's important for *these* cases to preallocate downloading files before
bittorrent started and do it (preallocation) *carefully*.

But when you use a bittorrent client for typical situations like downloading
into a hard drive or a SSD it useless to invoke this utility (doing any
preallocations is useless).
