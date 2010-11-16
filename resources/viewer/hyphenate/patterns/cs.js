﻿// For questions about the Czech hyphenation patterns
// ask Martin Hasoň (martin dot hason at gmail dot com)
Hyphenator.languages['cs'] = {
	leftmin : 2,
	rightmin : 2,
	shortestPattern : 1,
	longestPattern : 6,
	specialChars : "ěščřžýáíéúůťď",
	patterns : {
    	2 : "a11f1g1k1n1pu11vy11zé11ňó11š1ť1ú1ž",
    	3 : "_a2_b2_c2_d2_e2_g2_h2_i2_j2_k2_l2_m2_o2_p2_r2_s2_t2_u2_v2_z2_č2_é2_í2_ó2_š2_ú2_ž22a_a2da2ga2ia2ka2ra2sa2ta2u2av2aya2ča2ňa2ť2b_b1db1h1bib1j2bkb1m2bn1bob2z1bá1bí2bň2c_1ca2cc1ce1ci2cl2cn1coc2p2ctcy21cá1cí2cň1ců2d_1dad1bd1d1de1did1j2dkd1m2dn1dod1t1dud2v1dy1dá1dé1dě1dí2dň1dů1dý2e_e1ae1be1ee1ie2ke1o2ere1se1te1ue1áe2ňe1ře2šeú12f_f2l2fn2fr2fs2ft2féf2ú2g_2gngo12h_h2bh2c2hd2hkh2mh2rh1č2hňhř2h2ž2i_i1ai1bi1di1hi1ji1li1mi2ni1oi1ri1ti1xi1ái2ďi1éi1ói1ři2ši2ž2j_j2d1jij1j2jkj2m2jn2jp2jz2jď1jí2jž2k_k2dk2e2kf2kkk2l2kn2ks2kčk2ň2l_2lf2lg2lh1li2lj2lk2ll2ln2lp2lv2lz2lň1lů1lý2m_1ma1me2mf1mim2l2mn1mo2mp1mu2mv2mz2mčm2ž2n_2nb2nf2ngn1j2nk2nn2nz2nď2nónů22nž2o_o1ao1cog2o1ho1io1jo1lo1mo2no1oo1to2uo1xo2zo1čo2ňo1ř2p_2pkp2l2pn2pp2ptpá12pč2pš2pťqu22r_r1br1cr1d2rkr1l2rn2rrr1x2rzr1č2ró2rš2s_s2cs2d1se2sf1sis2js2k2sn1sos2p1sr2ss1sus2v1sé1sí2sň2sť1sůs2ž2t_1te2tf2tg1ti2tl2tm2tn1to2tpt2vt2č1té1tě2tř2tš1tů2u_u2b2ufu2ku2mu2nu2pu2ru2su2vu2zu2ču2ďu2ňu2šu2ž2v_2vkv2l2vm2vnv2p2vňwe22x_2xf2xnx1ty2ay2ey2sy2ňy2šyž22z_2zbz2ez2j2zl2ztz2v2zzzá12zč2zňz2řá1bá1dá1já1sá2ňá1řá2š2č_1ča2čb1če1či2čk2čn1čoč2p2čs1ču1čá1čí1čů2ď_1ďa1ďoé2dé2fé2lé2mé2sé2té2šé2žě1cě1lě2vě2zě1řě2šě2ťě2ží1bí1hí1jí1lí1rí1tí2ňí1ří2š2ň_2ňa2ňk2ňmň1só2z2ř_2řc2řdři12řk2řn1řoř2v2řz2řš2š_2šl2šnš2p2štš2vš2ň2ť_2ťk2ťm2ťtú2dú2kú2lú2nú2pú2tú2vú2zú2čú2žů1bů1cůt2ů2vů2zů2žý1bý1dý1hý1jý1lý2ný1rý1tý1uý1ř2ž_2žk2žl2žnž2v2žď2žň2žš",
    	4 : "_ch2_ná1_st2_us2_ut2_vy3_vý1_za3_zd2a3daa3dea3dia3doa3dua3dya3dáa3déa3děa3día3důa3dýa3gaa3goa3gua3gáah3va3ina3iva2jda2jmaj2oa3kea3kia3kla3koa3kra3kua3kya3káa3kéa3kóa3kůa3kýap3ta3raa3rea3ria3roa3rua3rya3ráa3róa3růa3rýa3saa3sea3sha3soa3sua3sva3sya3sáa3séa3sía3sůa3taa3tea3tia3toa3tra3tua3tva3tya3táa3téa3těa3tía3tóat1řa3tůa3týa3uja3učav3dav3taz3ka3zpa3čaa3čea3čia3čla3čoa3čua3čáa3čía3čůa3ňoa3ňua3říaú3t3ba_2b1cbe3pbis33bl_3blk2brib2ru2b1tbu2c3by_bys32b1č1bě_3bínb3řab1ří2bš2ce2u2ch_1cha3che2chl2cht1chu1chy1chá2chř2ck2c3lac3léc2tict2nc3tvc2těcuk11c2vda3dd2bad2bá2d1cde1xde2z2d1hd3kv3dl_d1lad3li1dlnd2lud1léd2lů1dmddo1ddo3hdo3pdo1sdo3tdo3čd1red3réd3rýd3tld3třdu3p2durd3ved3vld3vrd3vyd3vád3věd3víd3zbd3zdd3zn2d1č3dějd1řad1ří2dš2d3škd3št3dů_dů3sd2ž2e2are2břed1led3ve1hae1hee1hoe1hre1hue1hye1háe1hýe1jeej1mej1oej1uej3ve3kae3kee3koe3kre3kue3kye3káe3kée3kóe3kře3kůe1lae1lee1loe1lue1lye1láe1lée1líe1mle1mre1mye3máe1měe1míe3mře3můe1mýeo1seo3ze2plepy3e1rae1ree1rie1roer3se1rue1rye1ráe1rée1růe1rýe2ske2sles2me2stet1řeu3beu3deu3keu3meu3neu3peu3reu3teu3veu3zeu3že3vdevy3e3xue3zeez2te3zíe3zře1čte3ňoe3ňue3ňáe3óne3říe3šee3šie3šle3šoe3šíeú3neú3peú3teú3čf3líf1rige2s3gic3gin2g1mgu3mgu3vhe2she2uhe3x2hli2hlý2h2nh3ne2h1th2tě2h2vhyd1hys3ia3dib2li1chid2li1emi1eni1etif1ri2hlih3ni3imi2klik3milu3i3nai3nei3nii3noi3nui3nyi3nái3néi3něi3níi3nůi3nýi2psi1sais3cis1ti1syi3sáit1ri2tvi1umiv3di3zpiz1ri1člič3ti1íci1ími3šei3šiiš3ki3šoi3šui3šái3šíi3žai3žei3žii3žoi3žui3žája3dja3gj1b22j1cj3drj3dáj3důj3efj3ex2j1hj3kv2j1lj3maj3mi2jmíjne3j1obj1odj1ohj1opj1osj2ov2j1rj3sn2j1tj3tlju3pj1usju3tju3vju3zj1už2jv2j3vdj3vnj3zbj3zdj3zkj3znj3zp2j1čj3štj3šť2jú1jú3njú3čjú3ž3kaj3kat3kav3kač3kař2k1c3ket3kl_k3lék3lók3lý2k2mk3mě3kof3kovkr2s2k1tkt2r3kujku3v2k2v3kyn3kác3kár3kářk2ř23ků_1la_2l1b2l1c2l1dle2i1lej1lel3lio2ližl2kl2l1m1loslo3zl2pěls3n2l1t1lá_2l1č1lé_1lík1líř2lš2l3štlý2t2l2ž2m1b2m1cm2dl3me_me3x2mk22mleml3h2mlim3nam3nám3ném3nýmo2kmo2smoú3m2psmp2tmr2s2m1tmu3n2muš3má_má2sm2čemí1c2m2šmš3ť3mů_3mý_3na_na3hnat2na3zna3š2n1c2n1dne1dne1hne2jne3pne3zn3frng1l3nio2n1lno3z2nožn2sa2n1t2nub3ny_3nák2n1č2nív2níž2nš2n3što1bao1beob1lob1ro1buob3zo3béocy3od3bod1lod3vod1řo1e2oe3go2flo3gnoj2o2okaom2no3nao3neo3nio3noo3nuo3nyo3náo3něo3nío3nůo3nýo2pso1rao1reo1rio1roo1ruo1ryo1ráo3réo1růo3rýo1sao1sko1slo1syo3tío3třou3mou3vo3zaoz1bo3zeoz1ho3zioz3joz3koz1loz3mo3zooz3poz3to3zuo3zío3zůoč2ko3ňao3ňoo3ško3šlo3žl2p1c3pečp2kl3pl_pl3hp2nu3podpo3hpo3ppoč2pr2cpro1pr2sprů3p3tupá2c2př_při31ra_2rakr2blrca3r1harh3nr1hor3hur1há1ricr2kl2r1mro3h2r1sr2st2r1tr2thrtu31ru_1ry_ryd2rz3drz3l1rák1rářrč3t3ré_3rý_s2b2s3casch2s3cis3císe3h3sel3semset2se3zs3fo3sfés3fú3sic3sif3sik3sits3jus3ků3sl_3slns2lys1lís2mas2mos2nas2nes2ná2st_2stns2tvs2tás1tísy3csá2d3sáh2s2čs3čis3ťo1ta_1tajt1ao2t1b2t1c3te_2tihtiú32tiž2tk2t2klt2ká3tl_t1le3tlmtlu3t1lyt1lét2mat3níto3b2toj2trč2trý2t1sts2t2t1t1tu_1tuj2tup2tve1ty_3tá_t3či2tčí3tém2těh2těp1tíc1tím2tín2tírt1řut2řát3št1tý_1tým1týř3týšu2atu3bau3beu3biu3bou3buu3báu3bů2u2du3deu3diu3dou3duu3dyu3díu2hlu2inu2jmu3keu3kou3kuu3kyu3kůul1hu3mau3meu3miu3muu3má3umřu3neu3nou3nuu3něu3níu3nůu3pau3peu3piu3puu3pyu3páu3pěu3píu3půu3rau3reu3riu3ruu3rá1urču3růus1lu3sou3syu3sáu3síu3sůu3viu3vuu3zeu3ziuz1lu3zou3zuu3zíu3čau3čeu3čiu3čouč3tu3čuu3čáu3číu3šeu3šiu3šou3šuu3šáu3šíu3žeu3žou3žuu3žáu3ží2v1b2v1cv2ch2v2dv3di3venve2pv2kr2vlovo3bvo2svou3vr2cv1ro2vs2v1sk2v2tvy3cvyp2vy3tvy3čvyš2v2z22v2čv3čáv3čí3vín2vřív2š23výsvý3tv2ž23war3xovy2bly2chy2dry2gry3hny2kly3niy2přyr2vy3say3sey3siy3smy3soy3spys2ty3suy3svy3syy3sáy3séy3síyu3žy3vsy3zby3zdy3zky3zny3zpyč2kyř3by3říy3šey3šiy3škyš1ly3šoy3špy3šuy3šíy3ždza3hza3iza3jza3kzat2za3zza3šz2by2z1c2z2dz3dize3hzet2zev2ze3z2z2fz1ház3jí2z2kz3kyz3kéz3kůz3ký3zl_z2m22zmez3mnz3my2z2nz3noz3nuz3nyz3néz3něz3níz3ný2z2pz3ptz3tř3zu_zu3šz3vi3zy_záh23zápzá3zzáš2z3čl2zš2z3škz3štzú3čzú3žzů3sá2blá2dlád1řá1haá3heáh1láh3ná1hoá1hrá1háá1laá1leá1loá1luá1lyá3léá1líá3myá3méá1měá3míá3mýá1raá1reár2má1roá1ruá3růá2scá2smá2stát3kát1rá1tuá1tyá1tíá3týáz3ká3šeá3ší2č1c3če_če1cč3koč3kuč3ky2č1mč2neč1sk2č2t3čtvč3tí2ď1t3ďujé3dié3doé3foéf1ré2klé3maé3meé3mié3moé3mué3můé3taé3toé3táěd3rě3haě3heěh3ně1hoě3huě3hůě3jaě1jeě1joě3jůě1raě1reě1roěr3sě1ruě1ryě1růěs3kěs3nět1lě1trět3vě1tíě3vaě3veě3vlě3voě3vuě3váěv3čě3zeě3ziěz3ně3zoě3zíě3šeě3šiě3šoě3šuě3šáě3šíěš3ťě3ťoě3žeě3žiě3žoě3žuě3žííb3říd1lí2hlíh3ní2krí1máí3méí1měí1saít3kíz3kí3šeí3šií3šoí3šíňa3d3ňov2ň1tó3zaó3zió3zoó3zy2ř2bře1h2řesřia3ři3hřis2ři3zři3řř2kl2ř1l2ř1m2řou2ř2p2ř1s2ř1t2ř1č2řídří1sř3štšab32š1c2š2kš3kaš3ke3škrš3kyš2laš2liš2lošlá2š2léš2lý2š1m2š1sší3dš3ší2š2ťš3ťoš3ťuš3ťá3ťalú2c2úz3k3účeů1hlů3jdů1leů1myů1měů1raů1s2ů2stů3vaů3voů3věů3zoů3žeů3žiů3žoý1mlý1měý3noý1s2ý2ský3zký3znýš3lža3d3žač2ž1b2ž1c2ž1d3žil3žlo2ž1mžon22ž1t",
		5 : "_a4da_a4de_a4di_a4do_a4dé_a4kl_a4ko_a4kr_a4ku_a4ra_a4re_a4ri_a4ro_a4ry_a4rá_a4sa_a4se_a4so_a4sy_a4ta_a4te_at3l_a4to_a4tr_a4ty_a4ve_cyk3_dez3_d4na_dne4_d4ny_dos4_d4ve_d4vě_d4ví_e4ch_e4ko_es3k_es3t_e4ve_f4ri_h4le_h4ne_i4na_i4ni_i4no_is3l_j4ak_j4se_j4zd_jád4_k4li_k4ly_ne3c_neč4_ne3š_ni2t_n4vp_o4bé_ode3_od3l_o4ka_o4ko_o4na_o4ne_o4ni_o4no_o4nu_o4ny_o4ně_o4ní_o4pe_o4po_o4se_o4sl_ot3v_o4tí_o4tř_o4za_o4zi_o4zo_o4zu_o4šk_o4šl_o4ži_p4ro_p4rý_p4se_pu3b_rej4_re3s_ro4k_s4ch_s4ci_sem4_s4ke_sk4l_s4ká_s4le_s4na_s4ny_s4pe_s4po_s4tá_s4ži_u4ba_u4be_u4bi_u4bo_u4de_u4di_u4do_u4du_u4dí_uh4n_uj4m_u4ko_u4ku_ul4h_u4ma_u4me_u4mi_u4mu_u4ne_u4ni_u4pa_u4pe_u4pi_up4n_u4po_u4pu_u4pá_u4pě_u4pí_u4ra_u4ro_u4rá_u4so_u4st_u4sy_u4sí_u4vi_u4ze_u4če_u4či_u4čí_u4še_u4ši_u4šk_uš4t_u4ší_u4ži_už4n_u4žo_u4ží_v4po_v4zá_v4ži_y4or_y4ve_zar2_zač2_z4di_z4dr_z4ky_z4mn_z4no_z4nu_z4ně_z4ní_z4pe_z4po_z4tř_z4ve_z4vi_č4te_še3t_š4ka_š4ke_š4ky_š4ťo_š4ťá_ú4důaa3t2ab4lýab3riab4sbab2stac4ciad2laa4dlia4dláa4dléad4mead4muado4sad3ria3drža4dužad3voad4úzad4úřae4viafi2aag4faag3roah4liai4reaj4meak4nial4fbal4klal4tzal3žíam4bdam4klam4nuamo3sam4žia4naean4dtaneu4an4scan4sgan4slan4sman2span4svan4tčan4žhao4edao4hmao4tčap4r_a4psoa4př_ar4dwa4rerar4glar4kha4roxar3star2vaar3š2ar4šrarůs3a3sinas3náas3pia4stkas4tmas3tvat4cha4tioat4klat3loat3rea4truat4ráat4thau4gsauj4maus3tav4d_av3loa4vlua4vlíav4tiay4onaz3laaz4léaz3niač4máaře4ka4špla4špyba4brba3kaba4sebe4efbe4etbej4mbeu4rbe2z3beze3bi2b3bist4bi4trbl4blb2lemb2lesb4lánb2lémbo4etbo4jmbo4okbo4trbou3sbo4škb2ralb2ranb4roubroz4b3ru_b3rubb2rán2b1s2bs3trbtáh4bu4enby4smby4tčby4znbé4rcbě3tabí4rcb3ře_bře4scad4lca4escech4ced4lcelo3ce4nsce4ovce4pscer4v4che_ch4lych4mb2ch3n4chtech4u_cik4lc4ketco4atco4mmco4žpctis4ct4lací4plda4jšda4klda4trdch4ldd4hade3hnde3jdde3klde3kvde2nade2ozde3slde4smde4sode2spdes4tde4xtde3zndez3ode3čtde4žpdi4gg4dinddis3kdi4sodj4usd4labd4lakd2loud3lučd4láž2d1lídmýš44dobldo3bydo3bědo3býdod4ndoj4m4dokn4dolydo3mndo4pcdop4ndor2vdos4pdo3ukdo3učdo3z2doz4ndoč4tdo4žp4drand4rapd4rend3rosd3roud3rošdr4scd3rušd4rýv2d1s2ds4kůds4podum3řdu3nadu4pndu3sidu4í_d4vacdy4sudře4kd4řepd4řevd2řítea3dreb4erebez2eb4lie4ch_e4chme3choe2chre3chve4chťed4beed4kved2mae3dmned4říee4thee3xieg4giehno4eh4něej3age3jase3jede3jezej3ine3jisej3moe3jmue4klye4lauel4dvel4zee4mlíemo3kem3žeen4dven4scen4sient3reo3byeod3leo4due4oleeo2steo4třeo4zbeo4zdeoše3epa3te4pniep2noe4pnýep4tlep4tmep4tne4ptuer4a_er4s_er4sne4sage2scee4sinesi4ses4k_es3kyes3kée4slye4sp_es4pee4st_e4stee4tkie4tkre4tlie4tlyet3riet3roet3růet4úneu3cteu4m_eu4r_e4uraeu4rgeu3s2eu4tseve4še3v2ke4vskex4taey4orey4ovez4apez4boez3deez3duez4děez4ejez4elez4erez4esez4ezez4ešezis4ez4itez4leez4náez4něez4pyez4ácez4áhez4čeez4řeeč4tee4čtie4čtíeře4keř4kue4škaeš4láeš4toeúmy4ežíš4fe4infene4fe4uefi4emfi4flfló4rfm4nof4ranf4ras3frekfs4tefu4chga4učghou4gi4ímg4lomg4noig4nosgo4hm3grafgu4elgu4itgu4m_gus4tha4agha4arha4blha4brha3dlha4kehas3tha4ydhe4brhe4idhej4shi4anhi3erhi4ghhi4re4hla_h4ledh3lenh3lobh3loph3lovh3luj2h1ly4hlá_h4lásh3lí_4hlíkh4nedh3nivh4noj3hněd4hovehra4ph4tinh4títhu4chhu3mohu4tňhy4dohy4pshy4zdhř4byhý4blia3g2i4al_ias4tia4tri2b1ri4chžid4gei4dlýig4nei3hl_i4hliih4naijed4ij4meij4miik3leik4ryi4kveik4úřil4bai4lnui4mlai4mlyi4munina3din4cmin4dl3infein4ghin4gpin4gsin4gtin4špio4skiro4sis4chis4k_is3kais3keis3kris3kuis3kvis3kyis3lois3léis3plis3pois4thist3vis3tíit4rhit4rpit4seit4suix4tdič4tlič4toiř4kliř4čeiš4kriš4kviš4toja2b2jac4kja4cqj3aktj3dobj3dokj3dosjd4říjech4jg4raji4chjih3lji4mžj4inajis3kji2zvjod2řj4orajo3svj3ovljpor42j1s2j4semj4si_j4sk_js4kojs4kájs4poju4anju3naju3spju4t_ju4xtju3žijád2rjš4tika4blka4chka3dlka3ka3kami3kaněka2pska4pvka2přkas3tka4učkaš3lka4špke4blke3joke4prke4psk3lejk4libk3lic4klo_k3los2k3lyk3lá_kna4sko3byko4jmko2přko4skko3zá4kroak3robk3rofkr4ú_kuch4ku4fřku4hrku3seku3siku3suku4thk4vrňky2prkyp3řky4znká4plk3řejkš4tila4brlab4sla3kala4nqla4psla4všla4y_la2zmld4nele4adle4auleh3nle3jole4prle4psle4scle4smle4svlet3mle2trle4tčle4ukle4vhle4vkle3xilez3n3lhanli4azli4blli4bvli4dmlind4li4tňli4vrl4katlk4nul4nullo3brlo4idlo4islo3splo3svlo2trlo4třlo4u_loz4dlo4šk2l1s2l4slalst4nl4stílt4ralt4rult4rylu4idlu4j_lu4k_lu4lklu4m_lu4mnlu3prlu3valu3vllu3vylu3vílá4jšlá4všlí4pllí4znl4štýmaj4sma4klma4kr4maldmas3kmat3rma4všmaz3l2m1d2me4gome4ismh4lemid3lmik3rmi4xt3m2klmk4lamk4li4mla_ml4h_ml4scml4sk4mlu_mna4sm4nohm3nosm4noz3množm4nézm3nějmod3rmo2hlmo4s_mot3ř4moutmoza4mo3zřm4plompo4smp4se2m1s2m4stlmu4flmu4n_mu4ndmu4nnmu4nsmu4nšmy4škmálo3mí4rňmš4čina3chna4dona4emna4h_na3jdna3kana3p2na3s2na4s_na3tlna3třnaz4kna4zšna4č_naž4nn4chcnd4hindo4tnd2rend4rind4říne4glnej3tnej3une3klne3kvne4m_ne3s2ne4s_ne4ssne3tlnet4rne3udne3v2ne4v_nez4nne3škne3šťng4lang4leng4lín4grong4vinik4tni4mrni4mž3nisk2nitřno3b2no4bsno3hnno4hsno4irno4mžno3smnot4rno4zdno4šk2n1s2ns3akns4kon4socns3pont4r_nt3runt3ránu4ggná3s2ná4s_nš4ťooang4obe3jobe3sobe3zob4rňobys4o4chlo2chroc4keoc4koo4ct_oct3noc4únode3pode3so4docodos4od3raod3růo3držoe3tioh4neoi4ceo4into4jaro4jmio4jmuo4jmůo4juzok2teol4glol4toom4klona4soo4hřoote2o4ptuopá4to4př_o4raeor4dmor3stor4váorůs3o4saiose4sosi4do4skuosk3vo4skáo4skýos4laos4lios4lýos3moos4muo4st_o4stgo4stmo4stéo4stšo4stýot4klo4tlýoto3sot3root3víot3řiou3běou3děou4flou4ilou4isou4k_ou3kao4uklou3krou3káoup3noupo4ou4s_ou3saou3seou4skou3smou4tvou4vlou4vnouz3do4učkou3žio4vskovy2po2vštoz4d_oz3dáoz3děoz3díozer4oz4koo4zn_oz4pyoz4pěoz4píoz3rooz3ruoz3růo4zutoz3vroz3váozů4soč4kaoři2so4škuo4škyoš4láoš4mooš4tioš4ťuož4mopa4edpa4espa4klpa3sipa4t_pe4alpede4pe4igpe4npperi3pi4krpi4plpl4h_4plo_po1b2po3c2poly3po3m2po4mppo4olpo4p_po4pmpo1s2pos4ppo3t2po4t_po4tnpo3ukpo3učpo3už3po3vpo3z2po4zdpo3čkpo3řípo4šv4pra_prob2pro3ppro3z4pránpse4s2p1skp4sutp4tejp4terp4tevpt4rip4tá_pu4dlpu4trpyt3lpád3lpá4nvpá4slpé4rhpře3hpře3jpře3zpřih4pš4tira4brra4emra4esra4ffra4hlra4hmra4jgra4jšra4nhra3sira4vvra4wlra4y_ra4yora4ďm4ražir3char3chorc4kir4dlardo2sre4adre4aured4rre4etre3klre4mrre2sbres3lret4rre4umr3hl_ri4bbri4dgri4drri4flri4ghri4zmr4miorn4drro4adro3byrod2l3rofyro4h_ro4jbro4kšrom3nro2sbro3svro3tiro3tlro4tčro3vd3rovýroz3droz3nro4zoroz3vro3záro4čprpa3drr4harr4hor4stur4trárt4smr2t3vrt4zuru3seru3sirus3kru3žirych3rys3try4zkry4znry4í_ry4škrád4lrá4džrá3rirš4nírů4m_rů4v_rý4znsa4pfsa4prsas3ks3ce_sch4lsch4nsci4ese4ause4igse4ilsej4mse4kuse3lhse3s2ses4kse4ssse3tkse3třse4urse3čtsi4fl4skacs4kak4skams4kok2skonskos44skotsk4rask4rusk4ry4skvesk4vos3káns4lavs3le_s4leds3lems3lens3lets4libs3ly_s4meks3nats3ne_sn4tls3ná_s4nídsob4lso3brso4skso4tvsou3hsou3ssouz4so4šks4polss4sr4sta_s3tajs2tanst4at4stecs4tepst4er2stil4stičst3lo4sto_4str_4strnst4ve3ství4sty_s4tyl3styš4stá_s3tář4stě_s4těd3stěhs2těrs2těž2stí_su4basu4bosuma4su3vesá2klta2blt2a3dta4jfta4jg4talt4tand3taně2tarktast4ta4čkte4akte4flte4inteob4tep3lters4te4trte4ucte4urte4utti4grti3kltin4gti4plti3slti4tr2titutiz4r4tizít4kalt4kattk4latk4li4tkně4tla_tles3t3lo_t4loutlu4sto4astob4lto3drto4hmto4irtol4sto4ol4top_4topt4topu2torn2toupt4reat4reftre4ttrip4t4ritt4rogt3rolt4rou4trunt4rus4trášt3růmt3růvts4kott4chtt4ritu4fftu4lktu4r_tu3rytu4s_tu4ť_tu3ži2t3vit4višt4výcty4gřty2laty4řety4řhty4řjty4řoty4řrty4řútá4flté2bl2těnn4tíc_4tícet4řebt2řelt2řict3řiltř4ti3třábtří4stš4tiubs4tu3bí_uc4tíu3druue4fauh3láuh3nou3ka_uk4ajuk4aluk4atuk3lauk3leuk4á_ul4faul4píum4plum4ruun4dlun4žru3pln2u3rou3ry_us3kyus3káus3kéus3kýus2lou4steu4styu4stéu4stěu3střu4stšu4stýu3su_u4trou4tráuš4kluš3tíva3dlva4jťva4klv4dalv4děkv4děčve3jdve3psvep3řves3lve4smves4pvi4chvide2vi4drvi4etvi4krvi2tr4vle_4vlemv4nadvo4icvo4javo4jbvo4jdvo4jjvo4jmvo4jřvo4třvous2vr2dl4vrnyvr4stv3stvvy3d2vy3s2vy4snvys4tvyč4kvy4š_vy4šmvy4ššvy4žlvz4novz4névz4něvz4nívá3riv4čírvě4cmvíce3v3řínvše3s3vý3zwa4fdwa4rexand4xisk4xt4raxy4smyb3riy4chry2d1lyd4láyd4y_yh4neyj4mayj4meyk3layk4lyym4klyna4sype4ryp4siyp4táys3luys3teyst4ryt4meyvě4tyz4něyz4níyz4poyřk4nyř4čezab2lza4bsza4dkza3dlza4dnza4jkza4ktzal4kzam4nza3p2za3s2za3tlzat4rza4utzaz4nza4zšza4č_zaš4kza4šszban4zbys4zd4rezd4víze3p2ze3s2zes4pze3vnze4z_z4inez3ka_zlik3z3ly_z4měn3znakz4nalz3ne_z3nicz4nělz4nítz4nívzo4trzo4škz4pát3zrak2z1s2z4trázu3mozu3mězu3mízva4dz3vařzvik4zv4něz3vodz3vojz4vonzv4roz4vánz4věsz3víjzá3s2zřej3z3řezz3řešzš4ka2z2ú1áb4ryá4bř_á3choádo4sá3hl_á4jmuáj4můá4kliák4niáne4vá2s3kás4k_ás4klás4kná2slaás4lyás4poáv4siáv4síáz3niáz4viář4keář4kůča4brčes3kč3ka_čs4lačs4srčt4la4čtěnčís3lďs4te4ére_ě3hl_ěh3loě4kléě3k2těra3děrs4tět1a3ět4acět3raět3říěš4ťsí3choích4tíjed4íj4můí2s3kís4klís4knís4l_ís3leís4lnísáh2íz3daíz3deí3znařa4plřa4ďmře3chře3jdře3klře3kvřeo4rře3p2ře4p_ře4pkře4pčřer4vře2spře4srře3tlřet4řře3zdře3zk4řezlře3čtři4h_ři4hnři4jďři4l_ři4lbřil2n4řineři4v_ři4vkři4vnřič4tři4š_řk4lařk4liřk4lyřk4nořs4tořá4plřá2slří4křřš4tiša4vlšej4dšep3tši4mr4škovšk4roš3ku_š3livšmi4dš4tipšt4kašt4klš4těkš2těsš4těvš4típťáč4kúj4maút4koúře4zúš4tiůr4vaůr4vyůs3teů3tklý3choýd4laýt4kuýt4kyý4vliý4zvuýč4něža4tvže2b3žeh3nže4mlže4zgži4dlži4jmži2vlžk4niž4lic2ž1s2žá4bržá4nrží4znžš4tižš4tě",
		6 : "_ale3x_as3t3_je4dl_kří3d_le4gr_li3kv_moud3_na3č4_nář4k_od3rá_os4to_os4tě_ot3rá_ově4t_oz3do_pa4re_pa3tř_po3č4_roze3_roz3r_ru4dl_se3pn_va4dl_zao3sab3lona3d3ra3a3dvaa4nameane4skao4střas4tatat3ronat3rova4tří_ba4chr4chalgcien4c4dbat_3dch4nde4bredej4mode3strd3lou_4doboj4do4dd4do4djdomoh44do4čn3drobndře4pne3chl_eilus3ej3eleeju3steoch3repoč3te4s4knes3ku_e4s3lies3tižes4toles3táneu4rase4u4t_eu4traevy4čkevě4trezaos3ez3dovez4ed2eč4kateštíh4ha4dlahatos44h3lo_3hodinho3strhos4tě4hovna4hovny4hovná4hovněhy2t3rid4lo_ik3lo_ilič4nis3ko_i3slavis4talis4tatié4re_jbyst3jez3díjit4rojmou3dj1o3z2jpo4zvjpříz4j4s4kůj4s4mej4sou_j4soucj4s4teka2p3lka2p3rkast3r4k3la_4k3li_ko2t3vkous3k4la3silech3t4lejšk4lenchlepa3dlepo4slet4lilo3střma4tramet3remezi3smys3lonam4nene3h4nne4krones4le4nestino4skyno3strnst4rant4lemob3řezodej4modo4tkod4ranofrek4oje4dlo4jmovont4raopoč3topro4sopřej4o4s3keos4toros3trůoze3d2pat4ripes3t3pe4tra4p3la_4p3li_po3drupo3drápost4rpoč3tepra3stpro3t4pře3t4pře3č2rast4rre3kviretis4ric4kurna4všro3d4rromy4sropát4ro4skvro4skyrově4trs3tvěrs3tvý3rvanírys3kyrůs3ta3schopser4vase4střsig4nosi3ste4s3la_s4liči4s3lo_spro4ss4teros4tichs4tink4stit_s4tona4stou_4strams4trik4strács3třejsych3rsy4nesta3str4tenémtes3tatis4tr4t2kant3rant4tric_tro4sk4trouh4troň_4t4ružt3rálnt4vinntě3d4ltřeh3nupe2r3ve3dleve3stave3t4řve2z3m2v3la_vrst3vvy4dravě3t4aví4hatv3ští_y3klopymané4z4doba4zerotzlhos4ztros3zá4kl_ác3ti3ázni4cč4tenýě4trají3t3řeí3z3nií3zněnře4dobře4kříře3skaře3skořes3poře3staře3stuře3stáře3stř3ři4t_š3k3li4š3kouůs3tánýpo3č4",
		7 : "_dneš4k_mi3st4_no4s3t_os3t3r_polk4la4stru_b4roditckte4rýdob4ratdos4tivenitos4epro4zře4strouevyjad4evypá4t4kličkamš4ťan_nte4r3aonář4kaopře4jmovi4dlapodbě4hpod4nes4rčitý_se4strase4stru4stupnitac4tvovrs4tvězdně4níz4dobnýádos4tič4tené_č4tový_ů4jmový"
	}
};
