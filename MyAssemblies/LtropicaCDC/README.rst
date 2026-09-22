We reuse the data from the project  PRJNA484340 to rebuild the L.tropica CDC and L.aethiopica from the raw reads. The L.donovani assembly gave poor results both with Flye and Pecat with ~1000 contigs. So we only provide the rsults for L.tropica and L.aethiopica.

analysis made with LORA 1.0.0

for booking,we saved the AGP outputed by ragtag

For L.tropica, starting from raw data, we first use Flye (default parameter), we got 141 contigs. We scaffold onto Ld1S and got 76 contigs: that is 36 + maxicircle (18975bp) + 39.
We then used PECAT and got 52 contigs. We scaffold on Ld1S and got 44 contigs (maxicircle 29614bp)

Then, we filtered and rerun. With Flye, we got 132 contigs. We scaffold onto Ld1S and got 68 contigs: that is 36 + maxicircle (18976bp) + 31.

Using filtered data and pecat, we got 48 contigs. scaffold on Ld1S gave 42 contigs (maxicirlce 29591)
